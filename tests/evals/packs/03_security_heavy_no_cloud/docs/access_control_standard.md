# Ironvale Mutual Savings Bank - Access Control Standard (SYNTHETIC)

- Active Directory is the identity provider; single sign-on through SAML for internal applications.
- MFA is mandatory for all staff; privileged users authenticate with hardware key tokens.
- Least privilege with role-based profiles; access review every 90 days; privileged access management vault
  with session recording and just-in-time elevation.
- Service accounts are inventoried, stored in the PAM vault and subject to credential rotation every 60 days.
