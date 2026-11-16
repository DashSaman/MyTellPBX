# MytelPBX installer — https://mytel.one
# Pure Rocky OS only. Storage and OS root account remain normal Anaconda choices.
# There is deliberately no clearpart, autopart, default rootpw or embedded key.
graphical
cdrom
lang en_US.UTF-8
keyboard us
timezone Asia/Tehran --utc
network --bootproto=dhcp --activate --onboot=yes
skipx
reboot --eject

%packages
@^minimal-environment
policycoreutils
%end

%post --nochroot --erroronfail
set -eu
umask 077
target=/mnt/sysroot
source=/run/install/repo/mytelpbx
test -d "$target/etc"
test ! -e "$target/var/lib/mytelpbx-media"
test ! -L "$target/var/lib/mytelpbx-media"
install -d -m 0700 "$target/var/lib/mytelpbx-media"
cp -a "$source/depot/." "$target/var/lib/mytelpbx-media/"
install -d -m 0755 "$target/usr/local/libexec/mytelpbx"
install -m 0644 "$source/media-firstboot.py" "$target/usr/local/libexec/mytelpbx/media-firstboot.py"
install -m 0600 "$source/mytelpbx-media.json" "$target/etc/mytelpbx-media.json"
install -m 0644 "$source/mytelpbx-firstboot.service" "$target/usr/lib/systemd/system/mytelpbx-firstboot.service"
install -d -m 0755 "$target/etc/systemd/system/multi-user.target.wants"
ln -s /usr/lib/systemd/system/mytelpbx-firstboot.service "$target/etc/systemd/system/multi-user.target.wants/mytelpbx-firstboot.service"
install -d -m 0755 "$target/etc/systemd/system/issabel-firstboot.service.d"
install -m 0644 "$source/issabel-firstboot-media.conf" "$target/etc/systemd/system/issabel-firstboot.service.d/10-mytel-media.conf"
chroot "$target" /sbin/restorecon -RF /var/lib/mytelpbx-media /usr/local/libexec/mytelpbx /etc/mytelpbx-media.json /usr/lib/systemd/system/mytelpbx-firstboot.service /etc/systemd/system/issabel-firstboot.service.d
# Verify bytes only: no PBX install, service start, AMI or DB work inside Anaconda.
chroot "$target" /usr/libexec/platform-python -I -S -B /usr/local/libexec/mytelpbx/media-firstboot.py --verify
%end
