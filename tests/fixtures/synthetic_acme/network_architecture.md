# Acme Widgets – Network Architecture (SYNTHETIC)

## Topology
The head office LAN is segmented into VLANs: VLAN 10 (users), VLAN 20 (servers), VLAN 30 (DMZ) and a
management VLAN 99. A FortiGate next-generation firewall sits at the internet edge with default deny
ingress rules. Firewall rule review happens quarterly.

IP plan: 10.10.0.0/16 head office, 10.20.0.0/16 branch, 192.168.50.0/24 guest wifi (WPA2-Enterprise with 802.1X).
Remote users connect via IPsec VPN with MFA (Okta). A bastion host in the management VLAN is the only
route to server consoles.

Core switch: core-sw-01.acme.internal (10.10.0.1). Dual ISP links with failover.
Contact: netops@acme-widgets.example, +1 555 010 2233.
