{ config, pkgs, ... }:
{
  services = {
    minecraft-server = {
    eula = true;
    declarative = true;
    openFirewall = true;
    serverProperties.max-players = 100;
};
  openssh = {
    settings.PasswordAuthentication = false;
    settings.KbdInteractiveAuthentication = false;
};
  ollama = {
    acceleration = "cuda";
};
  headscale = {
    address = "0.0.0.0";
    port = 10101;
    log.level = "json";
};
};
networking = {
    firewall = {
    enable = true;
};
};

}