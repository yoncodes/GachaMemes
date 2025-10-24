using CommandLine;
using OffsetFinder;
using Spectre.Console;
using Color = Spectre.Console.Color;

namespace JJKPP;

public class Options
{
    [Option('i', "input", Required = true, HelpText = "Input APK or XAPK file")]
    public string Input { get; set; } = string.Empty;

    [Option('m', "metadata", Required = false, HelpText = "Metadata file path (optional for APKs)")]
    public string? Metadata { get; set; }

    [Option('a', "arch", Required = false, Default = "arm64", HelpText = "Target architecture (arm64, arm32, x86_64)")]
    public string Architecture { get; set; } = "arm64";

    [Option('o', "output", Required = false, HelpText = "Output file for results (optional)")]
    public string? Output { get; set; }

    [Option('v', "verbose", Required = false, Default = false, HelpText = "Verbose output")]
    public bool Verbose { get; set; }
}

class Program
{
    static void Main(string[] args)
    {
        Parser.Default.ParseArguments<Options>(args)
            .WithParsed(Run)
            .WithNotParsed(_ => Environment.Exit(1));
    }

    static void Run(Options options)
    {
        try
        {
            AnsiConsole.Write(new FigletText("JJKPP").Centered().Color(Color.Cyan1));
            AnsiConsole.MarkupLine("[cyan]IL2CPP Offset Finder for Unity APKs[/]\n");

            // Check if file exists
            if (!File.Exists(options.Input))
            {
                AnsiConsole.MarkupLine($"[red]✗ Error:[/] File not found: {options.Input}");
                Environment.Exit(1);
            }

            var finder = new IL2CPPFinder();

            // === DEBUG OUTPUT ===
            Console.WriteLine("[DEBUG] Starting analysis...");
            Console.WriteLine($"[DEBUG] Input: {options.Input}");
            Console.WriteLine($"[DEBUG] Extension: {Path.GetExtension(options.Input)}");
            Console.WriteLine();

            Console.WriteLine("[DEBUG] Testing version detection...");
            try
            {
                var testVersion = VersionDetector.DetectFromApk(options.Input, null);
                Console.WriteLine($"[DEBUG] ✓ Version string: {testVersion.FullString ?? "NULL"}");
                Console.WriteLine($"[DEBUG] ✓ Metadata version: {testVersion.MetadataVersion?.ToString() ?? "NULL"}");
                Console.WriteLine($"[DEBUG] ✓ Mapped version: {testVersion.MappedVersion ?? "NULL"}");

                if (testVersion.IsMetadataEncrypted)
                    Console.WriteLine("[DEBUG] ✓ Encrypted: True (detected via header)");
                else
                    Console.WriteLine("[DEBUG] ✓ Encrypted: (pending deeper check in analyzer)");

            }
            catch (Exception ex)
            {
                Console.WriteLine($"[DEBUG] ✗ Version detection error: {ex.Message}");
                Console.WriteLine($"[DEBUG] Stack trace: {ex.StackTrace?.Split('\n')[0]}");
            }
            Console.WriteLine();
            // === END DEBUG ===

            AnalysisResult result;

            // Determine file type
            var ext = Path.GetExtension(options.Input).ToLowerInvariant();
            bool isXapk = ext == ".xapk";
            bool isApk = ext == ".apk";
            bool isBinary = !isXapk && !isApk;

            // Analyze with status spinner
            result = AnsiConsole.Status()
                .Start($"Analyzing [yellow]{Path.GetFileName(options.Input)}[/]...", ctx =>
                {
                    ctx.Spinner(Spinner.Known.Dots);
                    ctx.SpinnerStyle(Style.Parse("green"));

                    if (isXapk)
                    {
                        ctx.Status("Extracting XAPK...");
                        return finder.AnalyzeApk(options.Input, options.Architecture);
                    }
                    else if (isApk)
                    {
                        ctx.Status("Extracting APK...");
                        return finder.AnalyzeApk(options.Input, options.Architecture);
                    }
                    else
                    {
                        ctx.Status("Analyzing binary...");
                        return finder.AnalyzeBinary(options.Input, options.Metadata);
                    }
                });

 

            // Display results
            DisplayResults(result, options.Verbose);

        }
        catch (Exception ex)
        {
            // Escape markup characters
            var message = ex.Message.Replace("[", "[[").Replace("]", "]]");
            AnsiConsole.MarkupLine($"[red]✗ Error:[/] {message}");

            if (ex.InnerException != null)
            {
                var innerMessage = ex.InnerException.Message.Replace("[", "[[").Replace("]", "]]");
                AnsiConsole.MarkupLine($"[dim]{innerMessage}[/]");
            }

            Environment.Exit(1);
        }
    }

    static void DisplayResults(AnalysisResult result, bool verbose)
    {
        // Game detection info (if detected)
        if (result.DetectedGame != null)
        {
            var gamePanel = new Panel($"[green]{result.DetectedGame.Name}[/]")
            {
                Header = new PanelHeader("[bold]Detected Game[/]"),
                Border = BoxBorder.Rounded
            };
            AnsiConsole.Write(gamePanel);
            AnsiConsole.WriteLine();
        }

        // Version info - escape brackets for Spectre.Console markup
        var versionText = result.Version.ToString().Replace("[", "[[").Replace("]", "]]");
        var versionPanel = new Panel($"[cyan]{versionText}[/]")
        {
            Header = new PanelHeader("[bold]Unity Version[/]"),
            Border = BoxBorder.Rounded
        };
        AnsiConsole.Write(versionPanel);
        AnsiConsole.WriteLine();

        // Results table
        if (result.Matches.Count == 0)
        {
            AnsiConsole.MarkupLine("[yellow]⚠[/] No patterns matched");
            return;
        }

        var table = new Table()
            .Border(TableBorder.Rounded)
            .AddColumn(new TableColumn("[bold]Offset Name[/]").Centered())
            .AddColumn(new TableColumn("[bold]Address[/]").Centered())
            .AddColumn(new TableColumn("[bold]Source[/]").Centered());

        foreach (var match in result.Matches.OrderBy(m => m.Name))
        {
            var sourceColor = match.Source == "symbol" ? "green" : "cyan";
            table.AddRow(
                match.Name,
                $"[yellow]0x{match.Address:X}[/]",
                $"[{sourceColor}]{match.Source}[/]"
            );
        }

        AnsiConsole.Write(table);

        // === NEW: Extracted data output ===
        if (result.ExtractedData != null && result.ExtractedData.Any())
        {
            AnsiConsole.WriteLine();
            var extractedTable = new Table()
                .Border(TableBorder.Rounded)
                .Title("[bold yellow]Extracted Data[/]")
                .AddColumn(new TableColumn("[bold]Name[/]").Centered())
                .AddColumn(new TableColumn("[bold]Address[/]").Centered())
                .AddColumn(new TableColumn("[bold]Size[/]").Centered());

            foreach (var entry in result.ExtractedData)
            {
                extractedTable.AddRow(
                    entry.Name,
                    $"[yellow]0x{entry.Address:X}[/]",
                    $"{entry.Data.Length} bytes"
                );
            }

            AnsiConsole.Write(extractedTable);
        }



        // Analysis time
        var timeColor = result.AnalysisTime.TotalSeconds < 1 ? "green" : "yellow";
        AnsiConsole.WriteLine();
        AnsiConsole.MarkupLine($"[dim]Analysis completed in [{timeColor}]{FormatTime(result.AnalysisTime)}[/][/]");

        // Pattern info
        if (result.DetectedGame != null)
        {
            AnsiConsole.MarkupLine($"[dim]Using game-specific patterns for {result.DetectedGame.ShortName.ToUpperInvariant()}[/]");
        }
    }

    static string FormatTime(TimeSpan time)
    {
        if (time.TotalSeconds >= 1)
            return $"{time.TotalSeconds:F2}s";
        if (time.TotalMilliseconds >= 1)
            return $"{time.TotalMilliseconds:F2}ms";
        return $"{time.TotalMicroseconds:F0}µs";
    }

   
}