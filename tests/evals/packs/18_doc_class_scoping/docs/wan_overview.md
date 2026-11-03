# Silver Marmot Freight - WAN Overview (SYNTHETIC)

Each depot connects over an SD-WAN link to the hub; the hub firewall enforces a VLAN per depot function
(office VLAN, scanner VLAN, guest wifi). The WAN router at each site runs BGP to both carriers; the LAN switch
stack is managed by the hub firewall. The DMZ hosts the customer tracking portal behind a WAF.
