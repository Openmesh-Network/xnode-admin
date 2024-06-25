{ config, pkgs, ... }:
{
  services.minecraft-server = {
    eula = true;
    declarative = true;
    openFirewall = true;
    serverProperties.max-players = 100;
  };
  services.openssh = {
    settings.PasswordAuthentication = false;
    settings.KbdInteractiveAuthentication = false;
  };
  services.ollama = {
    acceleration = "cuda";
  };
  services.headscale = {
    address = "0.0.0.0";
    port = 10101;
    log.level = "json";
  };
}