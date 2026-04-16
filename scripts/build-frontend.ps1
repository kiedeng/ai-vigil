Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Push-Location frontend
try {
  npm install
  npm run build
}
finally {
  Pop-Location
}

