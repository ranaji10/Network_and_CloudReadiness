# Old Mill Paper Works - Data Centre Inventory (SYNTHETIC)

- Hypervisor: VMware vSphere 6.7 on 8 hosts; server inventory of 95 VMs with vCPU, RAM and OS version in the
  CMDB: Windows Server 2012 R2 and 2016, RHEL 7, a few Hyper-V hosts for test.
- Hardware: 2 SAN arrays (20 TB, 3k IOPS), tape library for backup, 2 core switches.
- Databases: SQL Server 2014 (database size 2 TB, MES), Oracle 11g (ERP, 1.5 TB), DB2 on the mainframe gateway.
- Application portfolio: MES (mission critical), ERP (tier 1), quality lab system (tier 2); application owner per system.
- Licences: Microsoft enterprise agreement and Oracle support contract; renewal date tracked by purchasing.
- Cost baseline: hardware amortization and annual cost per system in the capex plan; no TCO comparison yet.
- No containers, no infrastructure as code; change management by e-mail and a weekly CAB.
