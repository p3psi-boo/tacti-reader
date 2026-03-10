{
  description = "TactiReader development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python311;
        pythonEnv = python.withPackages (
          ps: with ps; [
            pyqt5
            pymupdf
          ]
        );
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [
            pythonEnv
          ];

          shellHook = ''
            echo "TactiReader dev shell is ready."
            echo "Run: python tactireader.py"
          '';
        };
      }
    );
}
