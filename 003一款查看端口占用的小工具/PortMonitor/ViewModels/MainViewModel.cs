using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Data;
using System.Windows.Input;
using System.Windows.Threading;
using PortMonitor.Models;
using PortMonitor.Services;

namespace PortMonitor.ViewModels;

public class MainViewModel : ObservableObject
{
    // ── Fields ────────────────────────────────────────────────────────

    private readonly DispatcherTimer _autoRefreshTimer;
    private bool _isQuerying;

    // ── Constructor ────────────────────────────────────────────────────

    public MainViewModel()
    {
        Connections = new ObservableCollection<ConnectionInfo>();
        BindingOperations.EnableCollectionSynchronization(Connections, new object());

        _autoRefreshTimer = new DispatcherTimer(DispatcherPriority.Background)
        {
            Interval = TimeSpan.FromSeconds(2)
        };
        _autoRefreshTimer.Tick += async (_, _) => await QueryPortAsync();

        CheckPortCommand = new RelayCommand(async () => await QueryPortAsync(), () => !_isQuerying);
        ClearResultsCommand = new RelayCommand(ClearResults);
        KillProcessCommand = new RelayCommand(async () => await KillSelectedProcessAsync(), () => HasSelection);
        CopyPidCommand = new RelayCommand(CopyPids, () => HasSelection);
        CopyCmdLineCommand = new RelayCommand(CopyCmdLine, () => SelectedConnection != null);
    }

    // ── Properties ─────────────────────────────────────────────────────

    private string _portText = string.Empty;
    public string PortText
    {
        get => _portText;
        set => SetProperty(ref _portText, value);
    }

    public string[] ProtocolFilterOptions { get; } = { "全部", "TCP", "UDP" };

    private int _selectedFilterIndex;
    public int SelectedFilterIndex
    {
        get => _selectedFilterIndex;
        set => SetProperty(ref _selectedFilterIndex, value);
    }

    private bool _isAutoRefresh;
    public bool IsAutoRefresh
    {
        get => _isAutoRefresh;
        set
        {
            if (SetProperty(ref _isAutoRefresh, value))
            {
                if (value)
                    _autoRefreshTimer.Start();
                else
                    _autoRefreshTimer.Stop();
            }
        }
    }

    private bool _showCmdLine = true;
    public bool ShowCmdLine
    {
        get => _showCmdLine;
        set
        {
            if (SetProperty(ref _showCmdLine, value))
                UpdateDetailText();
        }
    }

    private string _statusText = "就绪";
    public string StatusText
    {
        get => _statusText;
        set => SetProperty(ref _statusText, value);
    }

    private string _detailText = string.Empty;
    public string DetailText
    {
        get => _detailText;
        set => SetProperty(ref _detailText, value);
    }

    public ObservableCollection<ConnectionInfo> Connections { get; }

    private ConnectionInfo? _selectedConnection;
    public ConnectionInfo? SelectedConnection
    {
        get => _selectedConnection;
        set
        {
            if (SetProperty(ref _selectedConnection, value))
            {
                HasSelection = value != null;
                UpdateDetailText();
                ((RelayCommand)CopyCmdLineCommand).RaiseCanExecuteChanged();
            }
        }
    }

    private bool _hasSelection;
    public bool HasSelection
    {
        get => _hasSelection;
        set
        {
            if (SetProperty(ref _hasSelection, value))
            {
                ((RelayCommand)KillProcessCommand).RaiseCanExecuteChanged();
                ((RelayCommand)CopyPidCommand).RaiseCanExecuteChanged();
            }
        }
    }

    // ── Commands ───────────────────────────────────────────────────────

    public ICommand CheckPortCommand { get; }
    public ICommand ClearResultsCommand { get; }
    public ICommand KillProcessCommand { get; }
    public ICommand CopyPidCommand { get; }
    public ICommand CopyCmdLineCommand { get; }

    // ── Methods ────────────────────────────────────────────────────────

    private async Task QueryPortAsync()
    {
        if (_isQuerying) return;

        if (!int.TryParse(PortText, out int port) || port < 0 || port > 65535)
        {
            StatusText = "请输入有效的端口号 (0-65535)";
            return;
        }

        _isQuerying = true;
        ((RelayCommand)CheckPortCommand).RaiseCanExecuteChanged();
        StatusText = "查询中...";

        try
        {
            var results = await Task.Run(() =>
            {
                var filter = SelectedFilterIndex switch
                {
                    1 => ProtocolFilter.TcpOnly,
                    2 => ProtocolFilter.UdpOnly,
                    _ => ProtocolFilter.All
                };
                var tcp = filter is ProtocolFilter.All or ProtocolFilter.TcpOnly
                    ? NativeNetworkService.GetTcpConnections(port)
                    : new();
                var udp = filter is ProtocolFilter.All or ProtocolFilter.UdpOnly
                    ? NativeNetworkService.GetUdpConnections(port)
                    : new();

                var combined = new List<ConnectionInfo>(tcp.Count + udp.Count);
                combined.AddRange(tcp);
                combined.AddRange(udp);
                return combined;
            });

            // Group by process name to deduplicate
            var unique = results
                .GroupBy(r => (r.Pid, r.LocalAddress, r.Protocol))
                .Select(g => g.First())
                .ToList();

            // Update on UI thread
            Connections.Clear();
            foreach (var item in unique)
                Connections.Add(item);

            var now = DateTime.Now.ToString("HH:mm:ss");
            StatusText = unique.Count > 0
                ? $"端口 {port} 已占用，发现 {unique.Count} 条记录 | {now}"
                : $"端口 {port} 未被占用 | {now}";
        }
        catch (Exception ex)
        {
            StatusText = $"查询失败: {ex.Message}";
        }
        finally
        {
            _isQuerying = false;
            ((RelayCommand)CheckPortCommand).RaiseCanExecuteChanged();

            // If auto-refresh is on, ensure timer is running
            if (_isAutoRefresh && !_autoRefreshTimer.IsEnabled)
                _autoRefreshTimer.Start();
        }
    }

    private void ClearResults()
    {
        Connections.Clear();
        DetailText = string.Empty;
        SelectedConnection = null;
        StatusText = "已清空";
    }

    private void UpdateDetailText()
    {
        if (SelectedConnection != null && ShowCmdLine && !string.IsNullOrEmpty(SelectedConnection.CmdLine))
            DetailText = SelectedConnection.CmdLine;
        else
            DetailText = string.Empty;
    }

    private async Task KillSelectedProcessAsync()
    {
        if (SelectedConnection == null) return;

        var pid = SelectedConnection.Pid;
        if (pid <= 0)
        {
            StatusText = "无效的 PID";
            return;
        }

        var result = MessageBox.Show(
            $"确定要结束 PID {pid} ({SelectedConnection.ProcessName}) 吗？",
            "确认结束进程",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);

        if (result != MessageBoxResult.Yes) return;

        StatusText = "正在结束进程...";

        try
        {
            await Task.Run(() =>
            {
                try
                {
                    var process = Process.GetProcessById(pid);
                    process.Kill(true);
                }
                catch (InvalidOperationException)
                {
                    // process already exited
                }
                catch (UnauthorizedAccessException)
                {
                    throw new UnauthorizedAccessException("权限不足，请以管理员身份运行");
                }
            });

            StatusText = $"已结束进程 PID {pid}";
            await QueryPortAsync();
        }
        catch (Exception ex)
        {
            StatusText = $"结束进程失败: {ex.Message}";
            MessageBox.Show(ex.Message, "错误", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void CopyPids()
    {
        if (SelectedConnection == null) return;

        var pidStr = SelectedConnection.Pid.ToString();
        if (string.IsNullOrEmpty(pidStr)) return;

        try
        {
            Clipboard.SetText(pidStr);
            StatusText = $"已复制 PID: {pidStr}";
        }
        catch (Exception ex)
        {
            StatusText = $"复制失败: {ex.Message}";
        }
    }

    private void CopyCmdLine()
    {
        if (SelectedConnection?.CmdLine == null) return;

        try
        {
            Clipboard.SetText(SelectedConnection.CmdLine);
            StatusText = "已复制命令行";
        }
        catch (Exception ex)
        {
            StatusText = $"复制失败: {ex.Message}";
        }
    }

    public void OnSelectionChanged(ConnectionInfo? selectedItem)
    {
        SelectedConnection = selectedItem;
    }
}