{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs?ref=nixpkgs-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };
  outputs = { self, ... }@inputs:
    inputs.flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = inputs.nixpkgs.legacyPackages."${system}";
        buildInputs = with pkgs.python3Packages; [ pkgs.python3Packages.hatchling ];
        propagatedBuildInputs = with pkgs.python3Packages; [ gitpython psutil requests ];
      in
      {
        packages.default = pkgs.python3Packages.buildPythonPackage {
          inherit buildInputs propagatedBuildInputs;
          pname = "xnode-admin";
          version = "1.0.0";
          format = "pyproject";
          src = self;
        };
        apps.default = { type = "app"; program = "${self.packages."${system}".default}/bin/openmesh-xnode-admin"; };
      });
}