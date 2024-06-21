{ config, pkgs, ... }:
{
  services.minecraft-server = {
    enable = true;
    eula = true;
    declarative = true;
    openFirewall = true;
    serverProperties.max-players = 100;
  };
}