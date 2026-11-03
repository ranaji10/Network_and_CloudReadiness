# Old Mill Paper Works - Network and Security Notes (SYNTHETIC)

- Flat network: a single VLAN for offices, the mill floor and servers; no DMZ. The network diagram dates from 2015.
- Perimeter: an older firewall appliance with permissive outbound rules; RDP exposed to the internet for the MES vendor.
- Identity: Active Directory; no SSO for SaaS; MFA is not enforced except for the VPN.
- Logging: Windows event logs on each server; no central logging; no intrusion detection.
- Patching: quarterly patch cycle; no vulnerability scan.
- Encryption: internal web apps run on TLS 1.0 and unencrypted HTTP; database backups to tape are unencrypted.
- Backup: nightly to tape, offsite weekly; RPO 24h; restore test never performed.
- Wireless: one WPA2 PSK network shared by staff and visitors.
