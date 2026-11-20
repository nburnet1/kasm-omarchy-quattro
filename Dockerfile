# syntax=docker/dockerfile:1
# Experimental: Omarchy Quattro-flavored Arch image adapted for Kasm Workspaces.
# Caveats:
# - No official kasmweb/core-arch; Kasm runtime is layered manually.
# - KasmVNC is installed by extracting a Ubuntu .deb (glibc/dep mismatches possible on Arch).
# - Omarchy Quattro expects bare-metal/VM Arch + Hyprland/Quickshell (Wayland); Kasm uses Xvnc.
# - Upstream omarchy installer is not container-safe; this image does a partial best-effort setup.

ARG BASE_IMAGE=archlinux:base-devel
FROM ${BASE_IMAGE}

ARG KASMVNC_DEB_URL=https://github.com/kasmtech/KasmVNC/releases/download/v1.4.0/kasmvncserver_noble_1.4.0_amd64.deb
ARG OMARCHY_BRANCH=v4.5.0

ENV LANG=C.UTF-8 \
    LANGUAGE=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=Etc/UTC \
    HOME=/home/kasm-default-profile \
    STARTUPDIR=/dockerstartup \
    INST_SCRIPTS=/dockerstartup/install \
    KASM_VNC_PATH=/usr/share/kasmvnc \
    KASM_DEFAULT_PROFILE_HOME=/home/kasm-default-profile \
    DISPLAY=:1 \
    VNC_PORT=5901 \
    NO_VNC_PORT=6901 \
    AUDIO_PORT=4901 \
    VNC_COL_DEPTH=24 \
    VNC_RESOLUTION=1280x720 \
    MAX_FRAME_RATE=24 \
    VNCOPTIONS="-PreferBandwidth -DynamicQualityMin=4 -DynamicQualityMax=7 -DLP_ClipDelay=0" \
    VNC_PW=vncpassword \
    VNC_VIEW_ONLY_PW=vncviewonlypassword \
    START_PULSEAUDIO=0 \
    START_XFCE4=0 \
    START_DE=openbox \
    KASM_SVC_AUDIO=0 \
    KASM_SVC_AUDIO_INPUT=0 \
    KASM_SVC_UPLOADS=0 \
    KASM_SVC_GAMEPAD=0 \
    KASM_SVC_WEBCAM=0 \
    KASM_SVC_PRINTER=0 \
    KASM_SVC_SMARTCARD=0 \
    KASM_SVC_SSH_AGENT=0 \
    KASMVNC_AUTO_RECOVER=true \
    SHELL=/bin/bash \
    TERM=xterm \
    DISTRO=arch \
    KASM_RX_HOME=/dockerstartup/kasmrx \
    PERL5LIB=/usr/share/perl5

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Base system + deps commonly needed by Kasm startup/KasmVNC and a minimal desktop
RUN pacman -Syu --noconfirm && pacman -S --noconfirm --needed \
      bash ca-certificates curl wget git sudo openssl \
      xorg-server xorg-xset xorg-xauth xorg-xkbcomp xorg-setxkbmap xkeyboard-config \
      inetutils iproute2 procps-ng psmisc findutils grep sed gawk coreutils tar \
      libjpeg-turbo libwebp libpng pixman freetype2 fontconfig mesa libglvnd libxcrypt-compat libbsd \
      libx11 libxext libxfixes libxrandr libxtst libxdamage libxshmfence libxcursor libxi \
      xterm openbox ttf-dejavu dbus \
      perl perl-switch perl-yaml-tiny perl-list-moreutils perl-try-tiny \
      perl-datetime perl-datetime-timezone perl-data-dumper \
      pipewire pipewire-pulse alsa-utils \
      python python-pip perl-clone \
    && mkdir -p /tmp/hms && cd /tmp/hms \
    && curl -fsSL https://cpan.metacpan.org/authors/id/R/RO/ROKR/Hash-Merge-Simple-0.051.tar.gz -o hms.tar.gz \
    && tar xzf hms.tar.gz && cd Hash-Merge-Simple-* \
    && mkdir -p /usr/share/perl5/vendor_perl/Hash/Merge /usr/share/perl5/site_perl/Hash/Merge \
    && cp lib/Hash/Merge/Simple.pm /usr/share/perl5/vendor_perl/Hash/Merge/Simple.pm \
    && cp lib/Hash/Merge/Simple.pm /usr/share/perl5/site_perl/Hash/Merge/Simple.pm \
    && cd / && rm -rf /tmp/hms \
    && pacman -Scc --noconfirm

WORKDIR /tmp

# Install KasmVNC by extracting upstream .deb (best-effort on Arch)
RUN curl -fsSL "$KASMVNC_DEB_URL" -o /tmp/kasmvnc.deb \
    && mkdir -p /tmp/kasmvnc-extract \
    && cd /tmp/kasmvnc-extract \
    && bsdtar -xf /tmp/kasmvnc.deb \
    && bsdtar -xf data.tar.* -C / \
    && rm -rf /tmp/kasmvnc.deb /tmp/kasmvnc-extract \
    && (command -v vncserver >/dev/null 2>&1 || { [ -x /usr/bin/kasmvncserver ] && ln -sf /usr/bin/kasmvncserver /usr/bin/vncserver; } || true) \
    && (command -v vncserver >/dev/null 2>&1 || { [ -x /usr/bin/kasmvncserver ] && ln -sf /usr/bin/kasmvncserver /usr/local/bin/vncserver; } || true) \
    && mkdir -p /usr/share/perl5/vendor_perl /usr/local/lib/perl5/site_perl \
    && ( [ -d /usr/share/perl5/KasmVNC ] && cp -a /usr/share/perl5/KasmVNC /usr/share/perl5/vendor_perl/ || true ) \
    && ( [ -d /usr/share/perl5/KasmVNC ] && cp -a /usr/share/perl5/KasmVNC /usr/local/lib/perl5/site_perl/ || true ) \
    && ( [ -x /usr/bin/Xkasmvnc ] && ln -sf /usr/bin/Xkasmvnc /usr/bin/Xvnc || true ) \
    && ( [ -x /usr/bin/Xkasmvnc ] && ln -sf /usr/bin/Xkasmvnc /usr/sbin/Xvnc || true ) \
    && ( [ -x /usr/bin/Xkasmvnc ] && ln -sf /usr/bin/Xkasmvnc /usr/local/bin/Xvnc || true ) \
    && ( [ -x /usr/bin/kasmvncserver ] && ln -sf /usr/bin/kasmvncserver /usr/sbin/vncserver || true ) \
    && ( [ -x /usr/bin/kasmvncpasswd ] && ln -sf /usr/bin/kasmvncpasswd /usr/bin/vncpasswd || true ) \
    && (ldconfig || true)

# Kasm runtime scripts (from kasmtech/workspaces-core-images, copied into build context if present)
RUN mkdir -p $STARTUPDIR $INST_SCRIPTS $KASM_RX_HOME/Downloads /home/kasm-user /run/pcscd /var/run/pulse

COPY src/common/startup_scripts/ $STARTUPDIR/
COPY src/common/scripts/kasm_hook_scripts/ $STARTUPDIR/kasm_hook_scripts/
COPY src/common/install/kasm_vnc/kasmvnc.yaml /etc/kasmvnc/kasmvnc.yaml
COPY custom_startup.sh $STARTUPDIR/custom_startup.sh

RUN chmod +x $STARTUPDIR/*.sh $STARTUPDIR/generate_container_user $STARTUPDIR/custom_startup.sh 2>/dev/null || true \
    && chmod -R +x $STARTUPDIR/kasm_hook_scripts 2>/dev/null || true

# Users and profile layout expected by Kasm
RUN (id -u 1000 >/dev/null 2>&1 || useradd -m -u 1000 -s /bin/bash kasm-user) \
    && (getent group kasm-user >/dev/null 2>&1 || groupadd -g 1000 kasm-user || true) \
    && usermod -aG kasm-user kasm-user 2>/dev/null || true \
    && echo "kasm-user ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers \
    && mkdir -p /home/kasm-default-profile/Desktop /home/kasm-default-profile/Uploads /home/kasm-default-profile/Downloads \
    && mkdir -p /home/kasm-user/Desktop /home/kasm-user/Uploads /home/kasm-user/Downloads \
    && mkdir -p $KASM_VNC_PATH/www/Downloads \
    && ln -sf /home/kasm-user/Downloads $KASM_VNC_PATH/www/Downloads/Downloads \
    && cp -a /etc/kasmvnc/kasmvnc.yaml /home/kasm-default-profile/.vnc/kasmvnc.yaml 2>/dev/null || true \
    && chown -R 1000:0 /home/kasm-default-profile /home/kasm-user $KASM_RX_HOME 2>/dev/null || true \
    && chown -R 1000:0 $KASM_VNC_PATH/www/Downloads 2>/dev/null || true

# Fetch Omarchy (Quattro) source for reference/customization inside image
RUN git clone --depth 1 -b ${OMARCHY_BRANCH} https://github.com/basecamp/omarchy.git /opt/omarchy || true \
    && if [ -d /opt/omarchy ]; then \
         mkdir -p /home/kasm-default-profile/.local/share && \
         cp -a /opt/omarchy /home/kasm-default-profile/.local/share/omarchy && \
         chown -R 1000:0 /home/kasm-default-profile/.local/share || true; \
       fi

# Attempt to install key Omarchy/Hyprland packages (may be large/partial; non-fatal best effort)
RUN pacman -S --noconfirm --needed \
      hyprland hyprland-guiutils hyprpicker hyprsunset xdg-desktop-portal-hyprland \
      quickshell wayland wl-clipboard grim slurp foot alacritty \
      pipewire wireplumber polkit networkmanager \
    || echo "WARN: some Omarchy/Hyprland packages unavailable; continuing"

# Basic cert/pw bootstrap helpers expected by vnc_startup in some flows (it also generates at runtime)
RUN mkdir -p /home/kasm-user/.vnc /home/kasm-default-profile/.vnc \
    && touch $STARTUPDIR/vnc_startup.log $STARTUPDIR/window_manager_startup.log \
    && chmod 666 $STARTUPDIR/vnc_startup.log $STARTUPDIR/window_manager_startup.log || true

# Try to make kasm default profile scripts compatible if they expect bashisms/paths
RUN bash $STARTUPDIR/set_user_permission.sh $STARTUPDIR $HOME 2>/dev/null || true

ENV HOME=/home/kasm-user
WORKDIR /home/kasm-user
EXPOSE 5901 6901 4901
USER 1000

ENTRYPOINT ["/dockerstartup/kasm_default_profile.sh", "/dockerstartup/vnc_startup.sh"]
CMD ["--wait"]
