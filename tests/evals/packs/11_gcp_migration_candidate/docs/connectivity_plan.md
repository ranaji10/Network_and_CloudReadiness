# Copperfield Marine Insurance - Hybrid Connectivity Plan (SYNTHETIC)

- Dedicated Interconnect (2 x 10 Gbps) to the cloud region plus a Cloud VPN site-to-site fallback; bandwidth
  requirement 3 Gbps peak, latency budget 8 ms for the claims database replication.
- IP plan: on-premises uses 10.0.0.0/8 subnets per site; 10.128.0.0/10 is reserved address space for the VPC design,
  non-overlapping with every existing CIDR.
- Identity federation: directory sync from Active Directory to Cloud Identity with SAML; workload identity for services.
- DNS: Cloud DNS private zones with forwarding; certificates through the internal PKI with ACME.
