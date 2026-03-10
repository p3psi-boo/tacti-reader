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
        python = pkgs.python314;
        qtPluginPath = "${pkgs.qt5.qtbase.bin}/lib/qt-${pkgs.qt5.qtbase.version}/plugins";
        pythonEnv = python.withPackages (
          ps: with ps; [
            markdown
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
            export QT_PLUGIN_PATH="${qtPluginPath}''${QT_PLUGIN_PATH:+:$QT_PLUGIN_PATH}"
            export QT_QPA_PLATFORM_PLUGIN_PATH="${qtPluginPath}/platforms"
            export QT_QPA_PLATFORM="xcb"
            echo "TactiReader dev shell is ready."
            echo "Run: python tactireader.py"
          '';
        };
      }
    );
}
