param([string]$Out = "C:\Users\Pedro\shot.png", [string]$Title = "Jefrey")
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices;
public class W {
  public delegate bool CB(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(CB cb, IntPtr l);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
  public struct RECT { public int L,T,R,B; }
}
"@
$pids = (Get-Process python*, Jefrey, Jefrey-Setup* -ErrorAction SilentlyContinue).Id
$found = New-Object System.Collections.ArrayList
$cb = [W+CB]{ param($h,$l)
  $sb = New-Object Text.StringBuilder 256; [W]::GetWindowText($h,$sb,256) | Out-Null
  $p2 = 0; [W]::GetWindowThreadProcessId($h,[ref]$p2) | Out-Null
  if ($pids -contains $p2 -and $sb.ToString() -like "$Title*" -and [W]::IsWindowVisible($h)) { [void]$found.Add($h) }
  return $true }
[W]::EnumWindows($cb, [IntPtr]::Zero) | Out-Null
if ($found.Count -eq 0) { "nenhuma janela '$Title' visivel"; exit 1 }
$h = $found[0]
$r = New-Object W+RECT; [W]::GetWindowRect($h, [ref]$r) | Out-Null
$w = $r.R - $r.L; $ht = $r.B - $r.T
$bmp = New-Object System.Drawing.Bitmap $w, $ht
$g = [System.Drawing.Graphics]::FromImage($bmp)
$dc = $g.GetHdc(); [W]::PrintWindow($h, $dc, 2) | Out-Null; $g.ReleaseHdc($dc)
$bmp.Save($Out)
"ok $w x $ht"
