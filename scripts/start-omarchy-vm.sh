#!/bin/bash
set -euo pipefail

disk=${OMARCHY_VM_DISK:-/vm/omarchy.qcow2}
iso=${OMARCHY_ISO:-/iso/omarchy.iso}
mkdir -p /vm "$HOME/.local/state/omarchy-vm"
if [[ ! -f "$disk" ]]; then
  qemu-img create -f qcow2 "$disk" "${OMARCHY_VM_DISK_SIZE:-40G}"
fi

firmware=/usr/share/edk2/x64/OVMF_CODE.4m.fd
variables=/vm/OVMF_VARS.4m.fd
if [[ ! -f "$variables" ]]; then
  cp /usr/share/edk2/x64/OVMF_VARS.4m.fd "$variables"
fi

args=(-name 'Omarchy Quattro' -machine q35 -m "${OMARCHY_VM_MEMORY:-4096}"
  -smp "${OMARCHY_VM_CPUS:-2}" -cpu max
  -drive "if=pflash,format=raw,readonly=on,file=$firmware"
  -drive "if=pflash,format=raw,file=$variables"
  -drive "file=$disk,if=virtio,format=qcow2"
  -device virtio-vga -device qemu-xhci -device usb-tablet
  -nic user,model=virtio-net-pci
  -display gtk,gl=off,show-cursor=on -full-screen
  -serial "file:$HOME/.local/state/omarchy-vm/serial.log")

if [[ -r /dev/kvm && -w /dev/kvm ]]; then
  args+=(-accel kvm)
else
  args+=(-accel tcg,thread=multi)
  printf '%s\n' 'KVM unavailable: using slower QEMU software emulation.' >&2
fi
if [[ -r "$iso" ]]; then
  args+=(-cdrom "$iso" -boot order=d,menu=on)
else
  args+=(-boot order=c,menu=on)
fi

exec qemu-system-x86_64 "${args[@]}"
