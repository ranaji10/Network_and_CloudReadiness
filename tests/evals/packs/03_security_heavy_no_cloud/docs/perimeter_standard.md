# Ironvale Mutual Savings Bank - Perimeter and Network Standard (SYNTHETIC)

- Internet ingress at both data centres terminates on a FortiGate next-generation firewall pair; default deny,
  documented allow list, firewall rule review every quarter and egress filter policies for servers.
- Public banking portal fronted by an Imperva web application firewall with DDoS scrubbing.
- Remote access only through the IPsec VPN with MFA; no direct exposure of management protocols.
- Network diagram and IP plan maintained by network engineering; zones: DMZ, application VLAN, database VLAN,
  branch WAN and a separate management network reachable through jump hosts.
- Branch offices: corporate wifi on WPA2-Enterprise with 802.1X; guest network isolated.
- Dual WAN links per site with failover; core switches in high availability pairs.
- Intrusion detection and intrusion prevention (Snort) inline at every zone boundary; EDR on every workstation.
