Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Push-Location frontend
try {
  npm install
  npm run dev -- --host 0.0.0.0 --port 5173
}
finally {
  Pop-Location
}

