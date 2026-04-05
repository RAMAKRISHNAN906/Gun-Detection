$dir = "c:\Users\ramak\Downloads\gun detection (new)\gun detection (new)"
Set-Location $dir
Start-Process -FilePath "python" -ArgumentList "app.py" -WorkingDirectory $dir -WindowStyle Normal
