package main

import (
	"archive/tar"
	"archive/zip"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

type nodeIndexEntry struct {
	Version string      `json:"version"`
	LTS     interface{} `json:"lts"`
}

func main() {
	args := os.Args[1:]

	root, err := appRoot()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	runtimeName, distName, archiveExt, err := platformNames()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	portableHome := root
	if err := ensurePortableHome(portableHome); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	runtimeDir := filepath.Join(root, "startup", "runtime", runtimeName)
	nodePath, npmPath := nodePaths(runtimeDir)
	codexEntry := filepath.Join(runtimeDir, "node_modules", "@openai", "codex", "bin", "codex.js")

	if _, err := os.Stat(codexEntry); err != nil {
		fmt.Println("[Codex] Bootstrapping local runtime...")
		if err := bootstrapRuntime(runtimeDir, nodePath, npmPath, distName, archiveExt); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	}

	exitCode := runCodex(nodePath, codexEntry, portableHome, args)
	os.Exit(exitCode)
}

func appRoot() (string, error) {
	if override := strings.TrimSpace(os.Getenv("CODEX_PORTABLE_ROOT")); override != "" {
		return filepath.Clean(override), nil
	}
	exe, err := os.Executable()
	if err != nil {
		return "", err
	}
	exe, err = filepath.EvalSymlinks(exe)
	if err != nil {
		return "", err
	}
	return filepath.Dir(exe), nil
}

func platformNames() (runtimeName string, distName string, archiveExt string, err error) {
	switch runtime.GOOS {
	case "windows":
		runtimeName = "windows"
		archiveExt = "zip"
		switch runtime.GOARCH {
		case "amd64":
			distName = "win-x64"
		case "arm64":
			distName = "win-arm64"
		default:
			return "", "", "", fmt.Errorf("unsupported windows arch: %s", runtime.GOARCH)
		}
	case "darwin":
		runtimeName = "macos"
		archiveExt = "tar.gz"
		switch runtime.GOARCH {
		case "amd64":
			distName = "darwin-x64"
		case "arm64":
			distName = "darwin-arm64"
		default:
			return "", "", "", fmt.Errorf("unsupported macos arch: %s", runtime.GOARCH)
		}
	case "linux":
		archiveExt = "tar.gz"
		switch runtime.GOARCH {
		case "amd64":
			runtimeName = "linux"
			distName = "linux-x64"
		case "arm64":
			runtimeName = "linux-arm"
			distName = "linux-arm64"
		case "arm":
			runtimeName = "linux-arm"
			distName = "linux-armv7l"
		default:
			return "", "", "", fmt.Errorf("unsupported linux arch: %s", runtime.GOARCH)
		}
	default:
		return "", "", "", fmt.Errorf("unsupported OS: %s", runtime.GOOS)
	}
	return runtimeName, distName, archiveExt, nil
}

func ensurePortableHome(home string) error {
	if err := os.MkdirAll(home, 0o755); err != nil {
		return err
	}
	for _, name := range []string{"log", "memories", "rules", "sessions", "skills", "tmp"} {
		if err := os.MkdirAll(filepath.Join(home, name), 0o755); err != nil {
			return err
		}
	}
	return nil
}

func nodePaths(runtimeDir string) (node string, npm string) {
	if runtime.GOOS == "windows" {
		return filepath.Join(runtimeDir, "node.exe"), filepath.Join(runtimeDir, "npm.cmd")
	}
	return filepath.Join(runtimeDir, "bin", "node"), filepath.Join(runtimeDir, "bin", "npm")
}

func bootstrapRuntime(runtimeDir, nodePath, npmPath, distName, archiveExt string) error {
	tmp, err := os.MkdirTemp("", "codex-portable-*")
	if err != nil {
		return err
	}
	defer os.RemoveAll(tmp)

	ver, err := latestNodeLTS()
	if err != nil {
		return err
	}

	archiveName := fmt.Sprintf("node-%s-%s.%s", ver, distName, archiveExt)
	base := fmt.Sprintf("https://nodejs.org/dist/%s", ver)
	archiveURL := fmt.Sprintf("%s/%s", base, archiveName)
	sumURL := fmt.Sprintf("%s/SHASUMS256.txt", base)

	archivePath := filepath.Join(tmp, archiveName)
	sumPath := filepath.Join(tmp, "SHASUMS256.txt")

	fmt.Printf("[Codex] Downloading Node.js %s (%s)...\n", ver, distName)
	if err := downloadFile(archiveURL, archivePath, 10*time.Minute); err != nil {
		return err
	}
	if err := downloadFile(sumURL, sumPath, 2*time.Minute); err != nil {
		return err
	}
	if err := verifySHA256(sumPath, archiveName, archivePath); err != nil {
		return err
	}

	if err := os.RemoveAll(runtimeDir); err != nil {
		return err
	}
	if err := os.MkdirAll(runtimeDir, 0o755); err != nil {
		return err
	}

	fmt.Println("[Codex] Extracting Node.js into app runtime...")
	if archiveExt == "zip" {
		if err := extractZipFlatten(archivePath, runtimeDir); err != nil {
			return err
		}
	} else {
		if err := extractTarGzFlatten(archivePath, runtimeDir); err != nil {
			return err
		}
	}

	if _, err := os.Stat(nodePath); err != nil {
		return fmt.Errorf("node runtime missing after extract: %s", nodePath)
	}

	fmt.Println("[Codex] Installing @openai/codex into app runtime...")
	env := os.Environ()
	env = append(env, fmt.Sprintf("PATH=%s%s%s", pathDir(runtimeDir), string(os.PathListSeparator), os.Getenv("PATH")))
	cmd := exec.Command(npmPath, "--prefix", runtimeDir, "install", "--no-audit", "--no-fund", "@openai/codex")
	cmd.Env = env
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin
	if err := cmd.Run(); err != nil {
		return err
	}
	return nil
}

func latestNodeLTS() (string, error) {
	client := &http.Client{Timeout: 30 * time.Second}
	req, err := http.NewRequest("GET", "https://nodejs.org/dist/index.json", nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("User-Agent", "codex-portable-launcher")

	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return "", fmt.Errorf("node index fetch failed: %s", resp.Status)
	}

	var entries []nodeIndexEntry
	if err := json.NewDecoder(resp.Body).Decode(&entries); err != nil {
		return "", err
	}

	for _, entry := range entries {
		if entry.Version == "" {
			continue
		}
		if isLTSTruthy(entry.LTS) {
			return entry.Version, nil
		}
	}
	return "", errors.New("no Node.js LTS version found in index.json")
}

func isLTSTruthy(value interface{}) bool {
	switch v := value.(type) {
	case bool:
		return v
	case string:
		return strings.TrimSpace(v) != ""
	default:
		return value != nil
	}
}

func downloadFile(url, outPath string, timeout time.Duration) error {
	client := &http.Client{Timeout: timeout}
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return err
	}
	req.Header.Set("User-Agent", "codex-portable-launcher")
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("download failed: %s", resp.Status)
	}
	f, err := os.Create(outPath)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = io.Copy(f, resp.Body)
	return err
}

func verifySHA256(sumPath, filename, archivePath string) error {
	expected, err := shaFromSums(sumPath, filename)
	if err != nil {
		return err
	}
	actual, err := sha256File(archivePath)
	if err != nil {
		return err
	}
	if !strings.EqualFold(expected, actual) {
		return fmt.Errorf("sha256 mismatch for %s", filename)
	}
	return nil
}

func shaFromSums(sumPath, filename string) (string, error) {
	content, err := os.ReadFile(sumPath)
	if err != nil {
		return "", err
	}
	for _, line := range strings.Split(string(content), "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) < 2 {
			continue
		}
		if fields[len(fields)-1] == filename {
			return fields[0], nil
		}
	}
	return "", fmt.Errorf("sha256 not found in sums for %s", filename)
}

func sha256File(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

func extractZipFlatten(zipPath, dest string) error {
	r, err := zip.OpenReader(zipPath)
	if err != nil {
		return err
	}
	defer r.Close()

	for _, f := range r.File {
		name := f.Name
		if strings.HasSuffix(name, "/") {
			continue
		}
		rel := stripFirstPathElement(name)
		if rel == "" {
			continue
		}
		outPath := filepath.Join(dest, filepath.FromSlash(rel))
		if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
			return err
		}
		rc, err := f.Open()
		if err != nil {
			return err
		}
		mode := f.Mode()
		if mode == 0 {
			mode = 0o644
		}
		out, err := os.OpenFile(outPath, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, mode)
		if err != nil {
			rc.Close()
			return err
		}
		_, copyErr := io.Copy(out, rc)
		out.Close()
		rc.Close()
		if copyErr != nil {
			return copyErr
		}
	}
	return nil
}

func extractTarGzFlatten(tarGzPath, dest string) error {
	f, err := os.Open(tarGzPath)
	if err != nil {
		return err
	}
	defer f.Close()
	gzr, err := gzip.NewReader(f)
	if err != nil {
		return err
	}
	defer gzr.Close()
	tr := tar.NewReader(gzr)

	for {
		hdr, err := tr.Next()
		if err != nil {
			if errors.Is(err, io.EOF) {
				return nil
			}
			return err
		}
		if hdr == nil {
			continue
		}
		if hdr.Typeflag != tar.TypeReg && hdr.Typeflag != tar.TypeRegA {
			continue
		}
		rel := stripFirstPathElement(hdr.Name)
		if rel == "" {
			continue
		}
		outPath := filepath.Join(dest, filepath.FromSlash(rel))
		if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
			return err
		}
		mode := os.FileMode(hdr.Mode)
		if mode == 0 {
			mode = 0o644
		}
		out, err := os.OpenFile(outPath, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, mode)
		if err != nil {
			return err
		}
		if _, err := io.Copy(out, tr); err != nil {
			out.Close()
			return err
		}
		if err := out.Close(); err != nil {
			return err
		}
	}
}

func stripFirstPathElement(path string) string {
	path = strings.TrimLeft(path, "/")
	parts := strings.SplitN(path, "/", 2)
	if len(parts) < 2 {
		return ""
	}
	return parts[1]
}

func pathDir(runtimeDir string) string {
	if runtime.GOOS == "windows" {
		return runtimeDir
	}
	return filepath.Join(runtimeDir, "bin")
}

func runCodex(nodePath, codexEntry, portableHome string, args []string) int {
	cmdArgs := []string{codexEntry, "-c", "personality=pragmatic"}
	cmdArgs = append(cmdArgs, args...)

	cmd := exec.Command(nodePath, cmdArgs...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin

	env := os.Environ()
	env = append(env, fmt.Sprintf("CODEX_HOME=%s", portableHome))
	env = append(env, fmt.Sprintf("HOME=%s", portableHome))
	runtimeDir := filepath.Clean(filepath.Join(filepath.Dir(nodePath), ".."))
	if runtime.GOOS == "windows" {
		runtimeDir = filepath.Dir(nodePath)
	}
	env = append(env, fmt.Sprintf("PATH=%s%s%s", pathDir(runtimeDir), string(os.PathListSeparator), os.Getenv("PATH")))
	cmd.Env = env

	if err := cmd.Run(); err != nil {
		var exitErr *exec.ExitError
		if errors.As(err, &exitErr) {
			return exitErr.ExitCode()
		}
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	return 0
}
