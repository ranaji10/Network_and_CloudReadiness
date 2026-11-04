# Verdigris Clinic Network - Network Diagram Notes (SYNTHETIC)

Topology: each clinic has a flat LAN (one subnet 10.8.x.0/24 per clinic) linked to head office by IPsec VPN.
There is no DMZ; the patient portal is hosted by a vendor. Guest wifi shares the clinic SSID.
Head office has a management VLAN for switches and the firewall.
