Work in progress



---
Selecting an Interface
---
Start ESPythoNOW with no interface specified.

Check logs for

```
[ESPythoNOW] Home Assistant mode
Interface must be specified.
Available Interface(s)
	wlp2s0
Unavailable Interface(s)
```

Copy the available Interface to the "Wireless Interface" in the configuration menu. (wlp2s0 in this case)

Restart ESPythoNOW.

Check Logs again.

*NOTE*
* Wireless Interface must support monitor mode.
* Performance and advanced options dependent on driver/interface.




---
MQTT
---
* Received messages are published to `/ESPythoNOW/*SENDERMAC*/*RECEIVERMAC*`
* To send message, publish message to `/ESPythoNOW/send/*RECEIVERMAC*`

