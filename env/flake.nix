{
  description = "Python + FastAPI + Firebase application";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        pythonEnv = pkgs.python312.withPackages (ps: with ps; [
          fastapi
          uvicorn
          pydantic
          pydantic-settings
          email-validator
          python-multipart
          firebase-admin
          httpx
          requests
          python-jose
          cryptography
          python-dotenv
          typing-extensions
          pytest
          pytest-asyncio

	  psycopg2-binary
	  asyncpg
	  sqlalchemy
        ]);

      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            pythonEnv
            pkgs.firebase-tools
            pkgs.google-cloud-sdk
            pkgs.just
          ];

          shellHook = ''
            echo "Python $(python --version)"
            echo "Firebase CLI $(firebase --version)"
            echo ""
            echo "Quick-start:"
            echo "  uvicorn app.main:app --reload   # start dev server"
            echo "  firebase emulators:start        # start Firebase emulators"
          '';
        };

        packages.default = pkgs.stdenv.mkDerivation {
          pname = "fastapi-firebase-app";
          version = "0.1.0";
          src = ./.;

          buildInputs = [ pythonEnv ];
          nativeBuildInputs = [ pkgs.makeWrapper ];

          installPhase = ''
            mkdir -p $out/lib/app $out/bin
            cp -r . $out/lib/app
            makeWrapper ${pythonEnv}/bin/uvicorn $out/bin/serve \
              --set PYTHONPATH "$out/lib/app" \
              --add-flags "app.main:app --host 0.0.0.0 --port 8000"
          '';
        };

        apps.default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/serve";
        };
      }
    );
}

