#!/bin/bash
### every exit != 0 fails the script
set -e

APP_NAME=$(basename "$0")

# Keep this path in sync with /etc/profile.d/kasm_ssh_agent.sh, written by
# install_ssh_agent.sh.
KASM_SSH_AGENT_DIR=/tmp/.kasm-ssh-agent
KASM_SSH_AGENT_SOCK="$KASM_SSH_AGENT_DIR/ssh-agent.sock"

log () {
    if [ ! -z "${1}" ]; then
        LOG_LEVEL="${2:-DEBUG}"
        INGEST_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        echo "${INGEST_DATE} ${LOG_LEVEL} (${APP_NAME}): $1"
        if [ ! -z "${KASM_API_JWT}" ]  && [ ! -z "${KASM_API_HOST}" ]  && [ ! -z "${KASM_API_PORT}" ]; then
            set +e
            http_proxy="" https_proxy="" curl https://${KASM_API_HOST}:${KASM_API_PORT}/api/kasm_session_log?token=${KASM_API_JWT} --max-time 1 -X POST -H 'Content-Type: application/json' -d '[{ "host": "'"${KASM_ID}"'", "application": "Session", "ingest_date": "'"${INGEST_DATE}"'", "message": "'"$1"'", "levelname": "'"${LOG_LEVEL}"'", "process": "'"${APP_NAME}"'", "kasm_user_name": "'"${KASM_USER_NAME}"'", "kasm_id": "'"${KASM_ID}"'" }]' -k -s || true
            set -e
        fi
    fi
}

# Ensure common system binary dirs are in PATH (Arch puts kasmvnc in /usr/bin, some builds in /usr/sbin)
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH}"
if [ -x /usr/bin/vncserver ] && [ ! -e /usr/local/bin/vncserver ]; then ln -sf /usr/bin/vncserver /usr/local/bin/vncserver 2>/dev/null || true; fi
if [ -x /usr/bin/kasmvncserver ] && [ ! -e /usr/local/bin/kasmvncserver ]; then ln -sf /usr/bin/kasmvncserver /usr/local/bin/kasmvncserver 2>/dev/null || true; fi

no_proxy="localhost,127.0.0.1"

kasm_profile_sync_found=0
if [ -f /usr/bin/kasm-profile-sync ] && [ -f /usr/bin/kasm-profile-sync-2 ]; then
    kasm_profile_sync_found=1
fi

# Set lang values
if [ "${LC_ALL}" != "en_US.UTF-8" ] && [ -n "${LC_ALL:-}" ]; then
  export LANG=${LC_ALL}
  export LANGUAGE=${LC_ALL}
fi

# Dbus
export $(dbus-launch 2>/dev/null || true)

# dict to store processes
declare -A KASM_PROCS

# switch passwords to local variables
tmpval=${VNC_VIEW_ONLY_PW:-}
unset VNC_VIEW_ONLY_PW || true
VNC_VIEW_ONLY_PW=$tmpval
tmpval=${VNC_PW:-vncpassword}
unset VNC_PW || true
VNC_PW=$tmpval

BUILD_ARCH=$(uname -p)
if [ -z ${KASM_PROFILE_CHUNK_SIZE} ]; then
  KASM_PROFILE_CHUNK_SIZE=100000
fi

STARTUP_COMPLETE=0

######## FUNCTION DECLARATIONS ##########

function help (){
	echo "USAGE: vnc_startup.sh [-w|--wait] [-s|--skip] [-d|--debug]"
}

trap cleanup SIGINT SIGTERM SIGQUIT SIGHUP ERR

function pull_profile (){
	if [ -z "$KASM_PROFILE_LDR" ]; then
		return
	fi
	if [ -z "$kasm_profile_sync_found" ] || [ "$kasm_profile_sync_found" -eq 0 ]; then
		echo >&2 "Profile sync not available"
		sleep 3
		http_proxy="" https_proxy="" curl -k "https://${KASM_API_HOST}:${KASM_API_PORT}/api/set_kasm_session_status?token=${KASM_API_JWT}" -H 'Content-Type: application/json' -d '{"status": "running"}' || true
		return
	fi
	log "Downloading and unpacking user profile from object storage."
	set +e
	PROCESS_SYNC_EXIT_CODE=1
	case "$KASM_PROFILE_LDR" in
	0|1)
		if [[ $DEBUG == true ]]; then
			OUTPUT=$(http_proxy="" https_proxy="" /usr/bin/kasm-profile-sync --download /home/kasm-user --insecure --remote ${KASM_API_HOST} --port ${KASM_API_PORT} -c ${KASM_PROFILE_CHUNK_SIZE} --token ${KASM_API_JWT} --verbose 2>&1 )
		else
			OUTPUT=$(http_proxy="" https_proxy="" /usr/bin/kasm-profile-sync --download /home/kasm-user --insecure --remote ${KASM_API_HOST} --port ${KASM_API_PORT} -c ${KASM_PROFILE_CHUNK_SIZE} --token ${KASM_API_JWT} 2>&1 )
		fi
		PROCESS_SYNC_EXIT_CODE=$?
		while IFS= read -r line; do log "$line"; done <<< "$OUTPUT"
		sleep 3
		http_proxy="" https_proxy="" curl -k "https://${KASM_API_HOST}:${KASM_API_PORT}/api/set_kasm_session_status?token=${KASM_API_JWT}" -H 'Content-Type: application/json' -d '{"status": "running"}' || true
		;;
	2)
		http_proxy="" https_proxy="" /usr/bin/kasm-profile-sync-2 --action pull --ignore-ssl --report-status
		PROCESS_SYNC_EXIT_CODE=$?
		;;
	esac
	set -e
	if (( PROCESS_SYNC_EXIT_CODE > 1 )); then
		log "Profile-sync failed with a non-recoverable error." "ERROR"
		exit 1
	fi
	log "Profile load complete."
}

function profile_size_check(){
    if [ -z "$KASM_PROFILE_LDR" ]; then return; fi
    # minimal no-op loop disabled in this experimental image
    return
}

function cleanup () {
    kill -s SIGTERM $! 2>/dev/null || true
    exit 0
}

function start_kasmvnc (){
	log "Starting KasmVNC"
	DISPLAY_NUM=$(echo $DISPLAY | grep -Po ':\d+' || echo ":1")
	if [[ $STARTUP_COMPLETE == 0 ]]; then
	    (vncserver -kill $DISPLAY || kasmvncserver -kill $DISPLAY || true) &> $STARTUPDIR/vnc_startup.log || true
	    rm -rfv /tmp/.X*-lock /tmp/.X11-unix &>> $STARTUPDIR/vnc_startup.log || true
	fi
	rm -rf $HOME/.vnc/*.pid || true
	mkdir -p $HOME/.vnc
	echo "exit 0" > $HOME/.vnc/xstartup
	chmod +x $HOME/.vnc/xstartup
	# ensure compatible config
	if [ -f /etc/kasmvnc/kasmvnc.yaml ] && [ ! -s "$HOME/.vnc/kasmvnc.yaml" ]; then
		cp /etc/kasmvnc/kasmvnc.yaml "$HOME/.vnc/kasmvnc.yaml" 2>/dev/null || true
	fi

	VNCOPTIONS="${VNCOPTIONS:-} -select-de manual"
	VNCSERVER_BIN=""
	if command -v vncserver >/dev/null 2>&1; then VNCSERVER_BIN=$(command -v vncserver);
	elif command -v kasmvncserver >/dev/null 2>&1; then VNCSERVER_BIN=$(command -v kasmvncserver);
	elif [ -x /usr/bin/kasmvncserver ]; then VNCSERVER_BIN=/usr/bin/kasmvncserver; fi

	if [ -n "$VNCSERVER_BIN" ]; then
		PERL5LIB="${PERL5LIB:-/usr/share/perl5}" HOME="$HOME" "$VNCSERVER_BIN" $DISPLAY -depth ${VNC_COL_DEPTH:-24} -geometry ${VNC_RESOLUTION:-1280x720} -websocketPort ${NO_VNC_PORT:-6901} -httpd ${KASM_VNC_PATH:-/usr/share/kasmvnc}/www -sslOnly -FrameRate=${MAX_FRAME_RATE:-24} -interface 0.0.0.0 -BlacklistThreshold=0 -FreeKeyMappings $VNCOPTIONS >> $STARTUPDIR/vnc_startup.log 2>&1 || \
		PERL5LIB="${PERL5LIB:-/usr/share/perl5}" HOME="$HOME" "$VNCSERVER_BIN" $DISPLAY -depth ${VNC_COL_DEPTH:-24} -geometry ${VNC_RESOLUTION:-1280x720} -websocketPort ${NO_VNC_PORT:-6901} -httpd ${KASM_VNC_PATH:-/usr/share/kasmvnc}/www -sslOnly -FrameRate=${MAX_FRAME_RATE:-24} -interface 0.0.0.0 $VNCOPTIONS >> $STARTUPDIR/vnc_startup.log 2>&1
	else
		log "vncserver binary not found in PATH=$PATH" "ERROR"
		exit 1
	fi

	sleep 2
	KASM_PROCS['kasmvnc']=$(cat $HOME/.vnc/*${DISPLAY_NUM}.pid 2>/dev/null || pgrep -f "X.*${DISPLAY_NUM}" | head -1 || echo "")

	if command -v xset >/dev/null 2>&1; then
		DISPLAY=$DISPLAY xset -dpms || true
		DISPLAY=$DISPLAY xset s off || true
	fi
}

function start_window_manager (){
	echo -e "\n------------------ window manager startup ------------------"
	if [ "${START_DE}" == "openbox" ] ; then
		if command -v openbox-session >/dev/null 2>&1; then
			DISPLAY=:1 openbox-session > $STARTUPDIR/window_manager_startup.log 2>&1 &
		else
			DISPLAY=:1 openbox > $STARTUPDIR/window_manager_startup.log 2>&1 &
		fi
		KASM_PROCS['window_manager']=$!
	elif [ "${START_XFCE4}" == "1" ] || [ "${START_DE}" == "xfce4-session" ]; then
		if command -v startxfce4 >/dev/null 2>&1; then
			DISPLAY=:1 startxfce4 --replace > $STARTUPDIR/window_manager_startup.log 2>&1 &
			KASM_PROCS['window_manager']=$!
		fi
	else
		echo "No supported window manager configured; relying on custom_startup.sh"
	fi
}

function start_audio_out (){
	if [[ ${KASM_SVC_AUDIO:-0} == 1 ]]; then
		if [[ ! -x /dockerstartup/start-audio.sh ]]; then
			log "Audio bridge is missing; build Dockerfile.audio to enable browser audio." "ERROR"
			return
		fi
		VNC_PW="$VNC_PW" /dockerstartup/start-audio.sh > /tmp/kasm-audio.log 2>&1 &
		KASM_PROCS['kasm_audio_out']=$!
	fi
}
function start_audio_in (){ :; }
function start_upload (){ :; }
function start_gamepad (){ :; }
function start_webcam (){ :; }
function start_printer (){ :; }
function wait_on_printer (){ :; }
function start_pcscd (){ :; }
function start_smartcard (){ :; }
function start_ssh_agent (){ :; }
function ensure_recorder_running (){ :; }
function wait_for_network_devices (){ :; }

function custom_startup (){
	custom_startup_script=/dockerstartup/custom_startup.sh
	if [ -f "$custom_startup_script" ]; then
		if [ ! -x "$custom_startup_script" ]; then
			chmod +x "$custom_startup_script" || true
		fi
		"$custom_startup_script" > /tmp/custom_startup.log 2>&1 &
		KASM_PROCS['custom_startup']=$!
		log "Executed custom startup script."
	fi
}

# ---- main ----
if [[ ${1:-} =~ -h|--help ]]; then help; exit 0; fi
if [[ ${KASM_DEBUG:-0} == 1 ]] || [[ ${1:-} == --debug ]] || [[ ${2:-} == --debug ]]; then
  echo -e "\n------------------ DEBUG KASM STARTUP -----------------"
  export DEBUG=true
  set -x
fi

SKIP_STARTUP=false
if [[ ${1:-} == --skip ]] || [[ ${2:-} == --skip ]]; then SKIP_STARTUP=true; fi

mkdir -p "$HOME/.vnc" "$HOME/Uploads" "$HOME/Downloads" "$STARTUPDIR" || true

if [ -f $HOME/.bashrc ]; then source $HOME/.bashrc || true; fi

# Create cert for KasmVNC
if [ ! -f "${HOME}/.vnc/self.pem" ]; then
  openssl req -x509 -nodes -days 3650 -newkey rsa:2048 -keyout ${HOME}/.vnc/self.pem -out ${HOME}/.vnc/self.pem -subj "/C=US/ST=VA/L=None/O=None/OU=DoFu/CN=kasm/emailAddress=none@none.none" 2>/dev/null || true
fi

PASSWD_PATH="$HOME/.kasmpasswd"
rm -f $PASSWD_PATH || true
if command -v kasmvncpasswd >/dev/null 2>&1; then
  printf "%s\n%s\n" "$VNC_PW" "$VNC_PW" | kasmvncpasswd -u kasm_user -wo || true
  printf "%s\n%s\n" "$VNC_PW" "$VNC_PW" | kasmvncpasswd -u kasm_viewer -r || true
  chmod 600 $PASSWD_PATH 2>/dev/null || true
elif command -v vncpasswd >/dev/null 2>&1; then
  printf "%s\n%s\n" "$VNC_PW" "$VNC_PW" | vncpasswd -f > "$HOME/.vnc/passwd" 2>/dev/null || true
  chmod 600 "$HOME/.vnc/passwd" 2>/dev/null || true
fi

if [ "$SKIP_STARTUP" = true ]; then
  exec "${@:2}"
fi

start_kasmvnc
start_window_manager
custom_startup
start_audio_out

echo -e "\n\n------------------ KasmVNC environment started ------------------"
tail -f $HOME/.vnc/*${DISPLAY}.log $HOME/.vnc/*:1.log $STARTUPDIR/vnc_startup.log 2>/dev/null &
KASM_PROCS['tail_logs']=$!

if [[ ${1:-} == --wait ]] || [[ ${1:-} == "" ]]; then
  # simple wait loop
  while true; do
    sleep 5
    if [ -n "${KASM_PROCS['kasmvnc']:-}" ] && ! kill -0 "${KASM_PROCS['kasmvnc']}" 2>/dev/null; then
      log "kasmvnc process exited, attempting restart"
      start_kasmvnc || true
    fi
    if [ -n "${KASM_PROCS['kasm_audio_out']:-}" ] && ! kill -0 "${KASM_PROCS['kasm_audio_out']}" 2>/dev/null; then
      log "Audio bridge exited, attempting restart"
      start_audio_out
    fi
  done
else
  exec "$@"
fi
