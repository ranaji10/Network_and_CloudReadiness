# Silver Marmot Freight - Operations Runbook (SYNTHETIC)

- Monitoring: Zabbix monitoring with on-call rota; logging to a central syslog server; patching monthly;
  change management through the weekly CAB; runbook per service.
- Reference: the network diagram and CIDR list are kept in the shared drive (10.40.0.0/16 for depots).
- Hosts: 30 VMs on VMware, each recorded with vCPU count and OS version (Windows Server 2019, Ubuntu 22.04); the
  monitoring tool keeps utilization data (CPU usage) for every host.
- Backups: nightly backup with offsite copy; restore test yearly; the on-call engineer runs the monitoring checks.
