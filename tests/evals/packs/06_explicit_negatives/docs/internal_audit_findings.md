# Rustbucket Logistics - Internal Audit Findings, IT Controls (SYNTHETIC)

Scope: the depot network and the warehouse management system. Status of the findings is open.

1. Depot sites connect to the internet with no firewall; traffic goes straight from the ISP router to the LAN.
2. The warehouse server has SSH open to the internet and RDP exposed for the vendor.
3. The whole estate is a flat network; a single VLAN carries office, warehouse and CCTV traffic.
4. MFA is not enforced for e-mail or the ERP; there is no MFA on the VPN either.
5. Hard-coded credentials were found in the label-printing scripts and the team uses a shared admin account.
6. The ERP web interface still accepts TLS 1.0 and transfers to the carrier run over unencrypted FTP.
7. The customer-service chatbot repository contains a hardcoded API key and places credentials in prompt templates.
8. Backups exist (nightly backup to a USB disk) but there is no restore test and no offsite copy.
