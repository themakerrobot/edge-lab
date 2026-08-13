# 폴더 고르기 창 — 윈도우 최신(탐색기형) 창을 띄운다.
#
# System.Windows.Forms.FolderBrowserDialog 는 옛 트리 창이라 좁고 낯설다.
# 탐색기형 큰 창은 IFileOpenDialog 에 "폴더를 고른다" 옵션(FOS_PICKFOLDERS)을 준 것이라,
# COM 인터페이스를 직접 선언해야 한다. 아래 C# 이 그 일을 한다.
#
# 이 파일이 어떤 이유로든 실패하면(구형 윈도우, .NET 없음 등) 마지막에 옛 창으로 물러선다.
# 고른 경로는 표준출력에 한 줄로만 쓴다 — 취소하면 아무것도 안 쓴다.

$ErrorActionPreference = "Stop"

function Pick-Modern {
    $code = @"
using System;
using System.Runtime.InteropServices;

public static class TmPick
{
    [ComImport, Guid("43826D1E-E718-42EE-BC55-A1E261C37BFE"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IShellItem
    {
        void BindToHandler(IntPtr pbc, ref Guid bhid, ref Guid riid, out IntPtr ppv);
        void GetParent(out IShellItem ppsi);
        void GetDisplayName(uint sigdnName, out IntPtr ppszName);
        void GetAttributes(uint sfgaoMask, out uint psfgaoAttribs);
        void Compare(IShellItem psi, uint hint, out int piOrder);
    }

    // IFileOpenDialog — 메서드 순서가 곧 호출 규약이라 하나도 건너뛸 수 없다.
    [ComImport, Guid("D57C7288-D4AD-4768-BE02-9D969532D960"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IFileOpenDialog
    {
        [PreserveSig] int Show(IntPtr parent);                 // IModalWindow
        void SetFileTypes(uint cFileTypes, IntPtr rgFilterSpec);
        void SetFileTypeIndex(uint iFileType);
        void GetFileTypeIndex(out uint piFileType);
        void Advise(IntPtr pfde, out uint pdwCookie);
        void Unadvise(uint dwCookie);
        void SetOptions(uint fos);
        void GetOptions(out uint pfos);
        void SetDefaultFolder(IShellItem psi);
        void SetFolder(IShellItem psi);
        void GetFolder(out IShellItem ppsi);
        void GetCurrentSelection(out IShellItem ppsi);
        void SetFileName([MarshalAs(UnmanagedType.LPWStr)] string pszName);
        void GetFileName([MarshalAs(UnmanagedType.LPWStr)] out string pszName);
        void SetTitle([MarshalAs(UnmanagedType.LPWStr)] string pszTitle);
        void SetOkButtonLabel([MarshalAs(UnmanagedType.LPWStr)] string pszText);
        void SetFileNameLabel([MarshalAs(UnmanagedType.LPWStr)] string pszLabel);
        void GetResult(out IShellItem ppsi);
        void AddPlace(IShellItem psi, int fdap);
        void SetDefaultExtension([MarshalAs(UnmanagedType.LPWStr)] string pszDefaultExtension);
        void Close(int hr);
        void SetClientGuid(ref Guid guid);
        void ClearClientData();
        void SetFilter(IntPtr pFilter);
        void GetResults(out IntPtr ppenum);
        void GetSelectedItems(out IntPtr ppsai);
    }

    [ComImport, Guid("DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7")]
    private class FileOpenDialog { }

    private const uint FOS_PICKFOLDERS   = 0x00000020;
    private const uint FOS_FORCEFILESYSTEM = 0x00000040;   // 실제 폴더만 (라이브러리 제외)
    private const uint FOS_PATHMUSTEXIST = 0x00000800;
    private const uint SIGDN_FILESYSPATH = 0x80058000;

    // 지금 맨 앞에 있는 창(브라우저)을 알아내 그 자식으로 띄운다.
    // 부모 없이 띄우면 활성 창이 아니라서 제목줄·테두리가 흐리게 그려지고,
    // 브라우저 뒤로 숨어 버리기도 한다.
    [DllImport("user32.dll")] private static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr hWnd);

    public static string Choose(string title)
    {
        IntPtr owner = GetForegroundWindow();
        if (owner != IntPtr.Zero) SetForegroundWindow(owner);
        var dlg = (IFileOpenDialog)new FileOpenDialog();
        uint opts;
        dlg.GetOptions(out opts);
        dlg.SetOptions(opts | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST);
        if (!string.IsNullOrEmpty(title)) dlg.SetTitle(title);
        dlg.SetOkButtonLabel("이 폴더 쓰기");

        int hr = dlg.Show(owner);
        if (hr != 0) return "";                            // 취소

        IShellItem item;
        dlg.GetResult(out item);
        IntPtr p;
        item.GetDisplayName(SIGDN_FILESYSPATH, out p);
        string path = Marshal.PtrToStringAuto(p);
        Marshal.FreeCoTaskMem(p);
        return path ?? "";
    }
}
"@
    Add-Type -TypeDefinition $code -Language CSharp | Out-Null
    return [TmPick]::Choose("작업 폴더를 고르세요 - 새 폴더도 만들 수 있어요")
}

function Pick-Legacy {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing          # 아래 임시 창의 Size/Point 에 필요
    $f = New-Object System.Windows.Forms.FolderBrowserDialog
    $f.Description = "작업 폴더를 고르세요 (새 폴더도 만들 수 있어요)"
    $f.ShowNewFolderButton = $true
    # 맨 앞으로 끌어올릴 임시 창 — 없으면 이 창도 뒤에 숨어 흐리게 보인다
    $top = New-Object System.Windows.Forms.Form
    $top.TopMost = $true; $top.ShowInTaskbar = $false
    $top.Size = New-Object System.Drawing.Size(1, 1)
    $top.StartPosition = "Manual"
    $top.Location = New-Object System.Drawing.Point(-2000, -2000)
    $top.Show(); $top.Activate()
    try {
        if ($f.ShowDialog($top) -eq "OK") { return $f.SelectedPath }
    } finally { $top.Close(); $top.Dispose() }
    return ""
}

try {
    $picked = Pick-Modern
} catch {
    try { $picked = Pick-Legacy } catch { $picked = "" }
}

if ($picked) { [Console]::Out.Write($picked) }
