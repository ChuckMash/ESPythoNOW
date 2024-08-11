
# sudo bash prep.sh *iface* *channel*
# sudo bash prep.sh wlp1s0 8
ifconfig $1 down
iwconfig $1 mode monitor
ifconfig $1 up
iwconfig $1 channel $2

