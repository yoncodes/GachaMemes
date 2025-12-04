#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <stdbool.h>
#include <time.h>
#include "decryptor/proto.h"

#ifdef _WIN32
#include <windows.h>
#define SLEEP_MS(ms) Sleep(ms)
#include <direct.h>
#define PATH_SEP '\\'
#define mkdir(path, mode) _mkdir(path)
#else
#include <dirent.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#define SLEEP_MS(ms) usleep((ms) * 1000)
#define PATH_SEP '/'
#endif

// Forward declaration
bool decrypt_file(const char *in, const char *out);

// Global statistics
typedef struct {
    int total_files;
    int successful;
    int failed;
    FILE *error_log;
} ProcessStats;

ProcessStats g_stats = {0};

// Utility: Check if string ends with suffix
bool ends_with(const char *str, const char *suffix) {
    size_t str_len = strlen(str);
    size_t suffix_len = strlen(suffix);
    if (suffix_len > str_len) return false;
    return strcmp(str + str_len - suffix_len, suffix) == 0;
}

// Utility: Create directory recursively
void create_directories(const char *path) {
    char tmp[512];
    snprintf(tmp, sizeof(tmp), "%s", path);
    size_t len = strlen(tmp);
    
    if (len > 0 && tmp[len - 1] == PATH_SEP)
        tmp[len - 1] = 0;
    
    for (char *p = tmp + 1; *p; p++) {
        if (*p == PATH_SEP || *p == '/' || *p == '\\') {
            *p = 0;
            mkdir(tmp, 0755);
            *p = PATH_SEP;
        }
    }
    mkdir(tmp, 0755);
}

// Initialize error tracking system
void init_error_tracking(void) {
    mkdir("tmp", 0755);
    
    time_t now = time(NULL);
    struct tm *t = localtime(&now);
    char log_name[256];
    snprintf(log_name, sizeof(log_name), 
             "tmp/errors_%04d%02d%02d_%02d%02d%02d.log",
             t->tm_year + 1900, t->tm_mon + 1, t->tm_mday,
             t->tm_hour, t->tm_min, t->tm_sec);
    
    g_stats.error_log = fopen(log_name, "w");
    if (g_stats.error_log) {
        fprintf(g_stats.error_log, "=== Lua Decryption Error Log ===\n");
        fprintf(g_stats.error_log, "Time: %s", asctime(t));
        fprintf(g_stats.error_log, "========================================\n\n");
        fflush(g_stats.error_log);
    }
}

// Log error and save failed file to tmp/
void log_error(const char *input_path, const char *error_msg) {
    g_stats.failed++;
    
    // Extract filename
    const char *filename = strrchr(input_path, PATH_SEP);
    if (!filename) filename = strrchr(input_path, '/');
    if (!filename) filename = strrchr(input_path, '\\');
    filename = filename ? filename + 1 : input_path;
    
    // Copy failed file to tmp/
    char tmp_path[512];
    snprintf(tmp_path, sizeof(tmp_path), "tmp/%s", filename);
    
    FILE *in = fopen(input_path, "rb");
    if (in) {
        fseek(in, 0, SEEK_END);
        size_t size = ftell(in);
        fseek(in, 0, SEEK_SET);
        
        uint8_t *buf = malloc(size);
        if (buf) {
            fread(buf, 1, size, in);
            
            FILE *tmp = fopen(tmp_path, "wb");
            if (tmp) {
                fwrite(buf, 1, size, tmp);
                fclose(tmp);
                fprintf(stderr, "   Failed file saved: %s\n", tmp_path);
            }
            free(buf);
        }
        fclose(in);
        
        // Log to error file
        if (g_stats.error_log) {
            fprintf(g_stats.error_log, "[FAILED] %s\n", input_path);
            fprintf(g_stats.error_log, "  Error: %s\n", error_msg);
            fprintf(g_stats.error_log, "  Size: %zu bytes\n", size);
            fprintf(g_stats.error_log, "  Saved to: %s\n\n", tmp_path);
            fflush(g_stats.error_log);
        }
    }
    
    fprintf(stderr, "\nX ERROR: %s\n", filename);
    fprintf(stderr, "   Reason: %s\n", error_msg);
}

// Safe wrapper for decrypt_file with error handling
bool decrypt_file_safe(const char *input_path, const char *output_path) {
    g_stats.total_files++;
    
    const char *filename = strrchr(input_path, PATH_SEP);
    filename = filename ? filename + 1 : input_path;
    
    printf("\n[%d] %s\n", g_stats.total_files, filename);
    
    // Call decrypt_file (returns true on success)
    bool success = decrypt_file(input_path, output_path);
    
    if (success) {
        g_stats.successful++;
        printf("   ✓ Success\n");
    } else {
        log_error(input_path, "Decryption or validation failed");
    }

    SLEEP_MS(20);
    
    return success;
}

// Get output path with .luac extension
void get_output_path(const char *input_base, const char *input_file, 
                     const char *output_base, char *output_path, size_t output_size) {
    // Get relative path from input_base
    const char *relative = input_file;
    size_t base_len = strlen(input_base);
    
    if (strncmp(input_file, input_base, base_len) == 0) {
        relative = input_file + base_len;
        while (*relative == PATH_SEP || *relative == '/' || *relative == '\\') {
            relative++;
        }
    }
    
    // Build output path
    snprintf(output_path, output_size, "%s%c%s", output_base, PATH_SEP, relative);
    
    // Replace extension with .luac
    char *ext = strrchr(output_path, '.');
    if (ext) {
        if (ends_with(output_path, ".lua.bytes")) {
            // Find the .lua part
            char *lua_ext = ext;
            while (lua_ext > output_path && *(lua_ext - 1) != '.' && 
                   *(lua_ext - 1) != PATH_SEP && *(lua_ext - 1) != '/' && 
                   *(lua_ext - 1) != '\\') {
                lua_ext--;
            }
            if (lua_ext > output_path && *(lua_ext - 1) == '.') {
                lua_ext--;
                strcpy(lua_ext, ".luac");
            }
        } else {
            strcpy(ext, ".luac");
        }
    }
}

#ifdef _WIN32
void process_directory_win(const char *input_base, const char *current_dir, 
                           const char *output_base) {
    WIN32_FIND_DATAA fdata;
    char pattern[512];
    snprintf(pattern, sizeof(pattern), "%s\\*", current_dir);
    
    HANDLE hFind = FindFirstFileA(pattern, &fdata);
    if (hFind == INVALID_HANDLE_VALUE) return;
    
    do {
        if (strcmp(fdata.cFileName, ".") == 0 || strcmp(fdata.cFileName, "..") == 0) {
            continue;
        }
        
        char full_path[512];
        snprintf(full_path, sizeof(full_path), "%s\\%s", current_dir, fdata.cFileName);
        
        if (fdata.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            process_directory_win(input_base, full_path, output_base);
        } else if (ends_with(fdata.cFileName, ".luac") || 
                   ends_with(fdata.cFileName, ".lua.bytes")) {
            
            char output_path[512];
            get_output_path(input_base, full_path, output_base, 
                          output_path, sizeof(output_path));
            
            // Create output directory
            char *last_sep = strrchr(output_path, PATH_SEP);
            if (last_sep) {
                *last_sep = '\0';
                create_directories(output_path);
                *last_sep = PATH_SEP;
            }
            
            decrypt_file_safe(full_path, output_path);
        }
    } while (FindNextFileA(hFind, &fdata));
    
    FindClose(hFind);
}
#else
void process_directory_unix(const char *input_base, const char *current_dir,
                            const char *output_base) {
    DIR *dir = opendir(current_dir);
    if (!dir) return;
    
    struct dirent *entry;
    struct stat st;
    
    while ((entry = readdir(dir)) != NULL) {
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) {
            continue;
        }
        
        char full_path[512];
        snprintf(full_path, sizeof(full_path), "%s/%s", current_dir, entry->d_name);
        
        if (stat(full_path, &st) != 0) continue;
        
        if (S_ISDIR(st.st_mode)) {
            process_directory_unix(input_base, full_path, output_base);
        } else if (S_ISREG(st.st_mode) && 
                   (ends_with(entry->d_name, ".luac") || 
                    ends_with(entry->d_name, ".lua.bytes"))) {
            
            char output_path[512];
            get_output_path(input_base, full_path, output_base,
                          output_path, sizeof(output_path));
            
            // Create output directory
            char *last_sep = strrchr(output_path, PATH_SEP);
            if (last_sep) {
                *last_sep = '\0';
                create_directories(output_path);
                *last_sep = PATH_SEP;
            }
            
            decrypt_file_safe(full_path, output_path);
        }
    }
    
    closedir(dir);
}
#endif

// Print final statistics
void print_statistics(void) {
    printf("\n========================================\n");
    printf("PROCESSING COMPLETE\n");
    printf("========================================\n");
    printf("Total files:      %d\n", g_stats.total_files);
    printf("Successful:       %d", g_stats.successful);
    if (g_stats.total_files > 0) {
        printf(" (%.1f%%)", 100.0 * g_stats.successful / g_stats.total_files);
    }
    printf("\nFailed:           %d", g_stats.failed);
    if (g_stats.total_files > 0) {
        printf(" (%.1f%%)", 100.0 * g_stats.failed / g_stats.total_files);
    }
    printf("\n");
    
    if (g_stats.failed > 0) {
        printf("\n⚠ %d file(s) failed - check tmp/ directory\n", g_stats.failed);
    }
    
    if (g_stats.error_log) {
        fprintf(g_stats.error_log, "\n=== SUMMARY ===\n");
        fprintf(g_stats.error_log, "Total: %d, Success: %d (%.1f%%), Failed: %d (%.1f%%)\n",
                g_stats.total_files, g_stats.successful,
                g_stats.total_files > 0 ? 100.0 * g_stats.successful / g_stats.total_files : 0,
                g_stats.failed,
                g_stats.total_files > 0 ? 100.0 * g_stats.failed / g_stats.total_files : 0);
        fclose(g_stats.error_log);
        g_stats.error_log = NULL;
    }
}

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "Usage: %s <input> <output>\n\n", argv[0]);
        fprintf(stderr, "  <input>   single file or directory\n");
        fprintf(stderr, "  <output>  output file or directory\n\n");
        fprintf(stderr, "Supported: .luac, .lua.bytes\n");
        fprintf(stderr, "Directory mode preserves structure.\n");
        fprintf(stderr, "Failed files saved to tmp/\n");
        return 1;
    }

    const char *input = argv[1];
    const char *output = argv[2];

    init_error_tracking();

    // Check if input is directory
    #ifdef _WIN32
    DWORD attrib = GetFileAttributesA(input);
    bool is_dir = (attrib != INVALID_FILE_ATTRIBUTES && 
                   (attrib & FILE_ATTRIBUTE_DIRECTORY));
    #else
    struct stat st;
    bool is_dir = (stat(input, &st) == 0 && S_ISDIR(st.st_mode));
    #endif

    if (is_dir) {
        printf("Batch processing: %s\n", input);
        printf("Output: %s\n", output);
        printf("----------------------------------------\n");
        
        create_directories(output);
        
        #ifdef _WIN32
        process_directory_win(input, input, output);
        #else
        process_directory_unix(input, input, output);
        #endif
    } else {
        // Single file mode
        if (!ends_with(input, ".luac") && !ends_with(input, ".lua.bytes")) {
            fprintf(stderr, "Error: Unsupported file format\n");
            fprintf(stderr, "Only .luac and .lua.bytes supported\n");
            return 1;
        }
        
        // Create output directory if needed
        char *last_sep = strrchr(output, PATH_SEP);
        #ifdef _WIN32
        if (!last_sep) last_sep = strrchr(output, '/');
        if (!last_sep) last_sep = strrchr(output, '\\');
        #endif
        
        if (last_sep) {
            char dir[512];
            size_t dir_len = last_sep - output;
            strncpy(dir, output, dir_len);
            dir[dir_len] = '\0';
            create_directories(dir);
        }
        
        printf("Processing: %s\n", input);
        decrypt_file_safe(input, output);
    }

    print_statistics();
    return g_stats.failed > 0 ? 1 : 0;
}