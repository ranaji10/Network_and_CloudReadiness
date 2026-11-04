# Nimbus Orchard Holdings - Network Architecture (SYNTHETIC)

Current network diagram and topology, reviewed quarterly by the network team (netops@example.com).

## Zones and segmentation
- Security zones: DMZ, application, data and a dedicated management network. Each zone is a separate VLAN
  and subnet; east-west traffic between zones passes the next-generation firewall cluster (HA pair).
- Micro-segmentation is enforced inside the application zone with host-based policies.
- Management plane: out-of-band management VLAN reachable only through a bastion host; administrators
  work from privileged access workstations.
- Wireless: corporate wifi uses WPA3 with 802.1X; guest wifi is a separate guest network with internet only.

## IP plan / CIDR schema
| Zone | CIDR | Notes |
|---|---|---|
| DMZ | 192.0.2.0/26 | public ingress |
| App | 10.20.0.0/16 | private subnet |
| Data | 10.30.0.0/16 | RFC 1918 |
| Mgmt | 10.99.0.0/24 | out-of-band |
| Cloud reserve | 10.100.0.0/14 | non-overlapping address space reserved for the VPC design |

The routing table and address plan live in the IPAM tool and are exported to this document monthly.

## Perimeter
- Every internet ingress sits behind the next-generation firewall; rules are default deny with a documented allow list.
- Firewall rule review happens quarterly; egress filter rules restrict outbound traffic to approved destinations.
- Public web applications sit behind Cloud Armor (web application firewall) with DDoS protection.
- Remote access: IPsec VPN for engineers and a zero trust identity-aware proxy for web applications, both behind MFA.

## Connectivity and resilience
- Dual ISP uplinks with BGP failover; Partner Interconnect (2 x 10 Gbps) to the cloud region, latency under 5 ms.
- Load balancer pairs run in high availability mode; critical services are multi-zone.
- DNS: internal zones in Cloud DNS, public zones signed; certificates come from the internal PKI with ACME automation.
