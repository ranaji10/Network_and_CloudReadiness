# Saffron Comet Retail - IT Overview (SYNTHETIC)

- Network: a Palo Alto next-generation firewall at head office with default deny; stores connect over SD-WAN with
  IPsec VPN; network diagram and CIDR plan in the wiki; DMZ, store VLAN and POS VLAN segmentation; management VLAN with a jump host.
- Identity: Okta SSO with MFA; RBAC and a yearly access review.
- Logging: Splunk SIEM, 12 months log retention; Suricata IDS; monthly vulnerability scan with Nessus and a 30 day patching cadence.
- Incident response plan with a tabletop exercise last spring.
