{ config, pkgs, ...}:
{
  services.minecraft-server = {
    enable = true;
    eula = true;
    declarative = true;
    openFirewall = true;
    serverProperties.max-players = 100;
  };
  services.openssh = {
    enable = true;
    settings.PasswordAuthentication = false;
    settings.KbdInteractiveAuthentication = false;
  };
  services.ollama = {
    enable = true;
    acceleration = "cuda";
  };
  services.headscale = {
    enable = true;
    address = "0.0.0.0";
    port = 10101;
    log.level = "json";
  };
}