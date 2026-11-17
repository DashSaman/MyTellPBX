auth --useshadow --enablemd5
#selinux --enforcing
#firewall --enabled --service=mdns
firewall --disabled
selinux --disabled
#xconfig --startxonboot
skipx

#issabel 4 option
##autopart --type=plain --fstype=ext4
#clearpart --all
#part /boot --fstype ext4 --size=300
#part / --fstype ext4 --size=3000 --grow
#part swap --recommended
#services --enabled=NetworkManager --disabled=network,sshd
#services --enabled=network,sshd --disabled=kdump
network --bootproto dhcp
network  --hostname=issabel.local
#keyboard us
timezone --utc America/New_York


reboot --eject
#install
logging --level=debug
#bootloader --location=mbr
#bootloader --location=mbr --append="net.ifnames=0 biosdevname=0"

#12/5/23
##bootloader --location=mbr --timeout=3 --append="net.ifnames=0"

#clearpart --none --initlabel
#clearpart --all --initlabel

clearpart --all --initlabel
#part /boot --fstype ext3 --size=100
#part / --fstype ext3 --size=1024 --grow
#part swap --size=256 --grow --maxsize=768
autopart --type=plain --fstype=ext4

# Root password
#rootpw --iscrypted $6$K2nKf02kVKG68960$OywvoaViphSITuro/liKvCj7Pm/CH/xqzz/lsoXyaKSR1lYf0vHAqSUc483a9MCCBkIwfr/hNMfqwxqVO0OEg1


%addon com_redhat_kdump --disable
%end

%packages
#@^Issabel with Asterisk 18
@^issabelast20
@rbl
@guru
#-biosdevname
%end

%pre
hostname issabel.local
echo " " > /tmp/issabelinstall
%end

%post --nochroot
rm -f /mnt/sysimage/tmp/issabelinstall
#Activating the network interface
cd /etc/sysconfig/network-scripts/
#cd /mnt/sysimage/etc/sysconfig/network-scripts/
#INICIO COMENTARIO
#INTFCNET=`ls -A /sys/class/net/`
#for x in $INTFCNET
#do
#	case $x in
#		lo*)
#		;;
#
#		sit*)
#		;;
				
		# Since CentOS 7 the way of naming network interfaces change to "Consistent Network Device Naming"
		# wich implements a change in the usual name 'ethN' to others network names of the form:
		# en* for ethernet interfaces
		# wl* for wireless lan interfaces
		# ww* for wireless wan interfaces
		# sl* for lineal serial interfaces
#		eth*|en*|ww*|wl*|sl*)
#			sed -i -e "s/ONBOOT=no/ONBOOT=yes/" ifcfg-$x
#			cp /etc/sysconfig/network-scripts/ifcfg-$x /mnt/sysimage/etc/sysconfig/network-scripts/bck.ifcfg-$x.bck
#		;;
#	esac
#done 
#FIN COMENTARIO

#We have to disable ipv6
#sysctl -w net.ipv6.conf.all.disable_ipv6=1
#sysctl -w net.ipv6.conf.default.disable_ipv6=1

#Disable the CentOS progress bar
#cd /mnt/sysimage/boot/grub2/
#sed -i -e 's/ rhgb//' grub.cfg

# replace some strings
#cd /mnt/sysimage/etc
#sed -i -e 's/CentOS Linux 7 (Core)/Issabel 4/g' os-release
#sed -i -e 's/https://www.centos.org/www.issabel.org/g' os-release
#sed -i -e 's/CentOS Linux/Issabel PBX/g' os-release
#sed -i -e 's/0,31/0,35/g' os-release
#cd /mnt/sysimage/boot/grub2/
#sed -i -e 's/CentOS Linux/Issabel 4/g' grub.cfg
#sed -i -e 's/7 (Core)//g' grub.cfg
#cd /mnt/sysimage/boot/efi/EFI/centos
#sed -i -e 's/CentOS Linux/Issabel 4/g' grub.cfg
#sed -i -e 's/7 (Core)//g' grub.cfg

#Activating a compatible VGA Mode and commenting an option of menu
sed -i -e 's/hiddenmenu/#hiddenmenu/' grub.conf
#sed -i -e 's/ quiet/ quiet vga=0x318/' grub.conf

#Disable the mouse console
#cd /etc/rc.d/init.d
#./gpm stop
#chkconfig --level 23 gpm off

#Add Issabel 5 repo
#cp -p /run/install/repo/Issabel5.repo /mnt/sysimage/etc/yum.repos.d/

#Import GPG Keys
rpm --import --root /mnt/sysimage/ /run/install/repo/RPM-GPG-KEY-Issabel
rpm --import --root /mnt/sysimage/ /run/install/repo/RPM-GPG-KEY-rockyofficial
rpm --import --root /mnt/sysimage/ /run/install/repo/RPM-GPG-KEY-EPEL-8
rpm --import --root /mnt/sysimage/ /mnt/sysimage/etc/pki/rpm-gpg/RPM-GPG-KEY-remi.el8

#patch config files
echo " " >> /mnt/sysimage/etc/asterisk/res_odbc_additional.conf
echo " " >> /mnt/sysimage/etc/asterisk/res_odbc_custom.conf

cd /mnt/sysimage/
mkdir -p var/log/asterisk
mkdir -p var/log/asterisk/cdr-csv
mkdir -p var/lib/asterisk/sounds/custom
chroot /mnt/sysimage chown asterisk.asterisk /var/log/asterisk -R

chown -R asterisk.asterisk /mnt/sysimage/var/www/html
chown -R asterisk.asterisk /mnt/sysimage/etc/asterisk
chown -R asterisk.asterisk /mnt/sysimage/var/lib/asterisk
chown -R asterisk.asterisk /mnt/sysimage/var/log/asterisk

chmod 755 "/mnt/sysimage/var/lib/asterisk/agi-bin/*"

#necesario para updates futuros
chroot /mnt/sysimage dnf -y module enable php:remi-7.4
chroot /mnt/sysimage dnf -y config-manager --set-enabled remi
chroot /mnt/sysimage dnf -y config-manager --set-enabled powertools
chroot /mnt/sysimage dnf -y check-upgrade
chroot /mnt/sysimage rm -f /var/lib/dnf/modulefailsafe/iso:rolling:.yaml

#force issabelPBX install
touch /mnt/sysimage/installamp

#desactivo selinux

sed -i "s/SELINUX\=enforcing/SELINUX\=disabled/" /mnt/sysimage/etc/selinux/config 

grep $(chroot /mnt/sysimage hostname) /mnt/sysimage/etc/hosts || echo 127.0.0.1 localhost $(chroot /mnt/sysimage hostname) >> /mnt/sysimage/etc/hosts


#Fin chroot
%end
