param([switch]$Close)
Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices;
public class V { public delegate bool CB(IntPtr h, IntPtr l);
[DllImport("user32.dll")] public static extern bool EnumWindows(CB cb, IntPtr l);
[DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
[DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
[DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
public struct RECT { public int L,T,R,B; } }
"@
$pids = (Get-Process python*, Jefrey -ErrorAction SilentlyContinue).Id
$cb = [V+CB]{ param($h,$l)
  $sb = New-Object Text.StringBuilder 256; [V]::GetWindowText($h,$sb,256) | Out-Null
  $p2 = 0; [V]::GetWindowThreadProcessId($h,[ref]$p2) | Out-Null
  if ($pids -contains $p2 -and $sb.ToString().StartsWith("Jefrey")) { if ($Close -and $sb.ToString() -eq "Jefrey") { [V]::PostMessage($h, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null } $r = New-Object V+RECT; [V]::GetWindowRect($h,[ref]$r)|Out-Null; Write-Host ("'{0}' visible={1} {2}x{3} at {4},{5}" -f $sb, [V]::IsWindowVisible($h), ($r.R-$r.L), ($r.B-$r.T), $r.L, $r.T) }
  return $true }
[V]::EnumWindows($cb, [IntPtr]::Zero) | Out-Null
