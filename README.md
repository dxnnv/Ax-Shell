<p>
<a href="https://github.com/dxnnv/Ax-Shell">
  <img src="assets/cover.png" alt="Ax-Shell Banner Logo">
  </a>
</p>

<p>
  <sub><sup><img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Telegram-Animated-Emojis/main/Activity/Sparkles.webp" alt="Sparkles" width="25" height="25"/></sup></sub>
  <a href="https://github.com/hyprwm/Hyprland">
    <img src="https://img.shields.io/badge/A%20hackable%20shell%20for-Hyprland-0092CD?style=for-the-badge&logo=linux&color=0092CD&logoColor=D9E0EE&labelColor=000000" alt="A hackable shell for Hyprland">
  </a>
  <a href="https://github.com/Fabric-Development/fabric/">
    <img src="https://img.shields.io/badge/Powered%20by-Fabric-FAFAFA?style=for-the-badge&logo=python&color=FAFAFA&logoColor=D9E0EE&labelColor=000000" alt="Powered by Fabric">
  <sub><sup><img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Telegram-Animated-Emojis/main/Activity/Sparkles.webp" alt="Sparkles" width="25" height="25"/></sup></sub>
  </a>
  </p>

  <p>
  <a href="https://github.com/Axenide/Ax-Shell/stargazers">
    <img src="https://img.shields.io/github/stars/Axenide/Ax-Shell?style=for-the-badge&logo=github&color=E3B341&logoColor=D9E0EE&labelColor=000000" alt="GitHub stars">
  </a>
  <a href="https://ko-fi.com/Axenide">
    <img src="https://img.shields.io/badge/Support Axenide on-Ko--fi-FF6433?style=for-the-badge&logo=kofi&logoColor=white&labelColor=000000" alt="Ko-Fi">
  </a>
  <a href="https://discord.com/invite/gHG9WHyNvH">
    <img src="https://img.shields.io/discord/669048311034150914?style=for-the-badge&logo=discord&logoColor=D9E0EE&labelColor=000000&color=5865F2&label=Discord" alt="Discord">
  </a>
</p>

---

<h2><sub><img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Camera%20with%20Flash.png" alt="Camera with Flash" width="25" height="25" /></sub> Screenshots</h2>
<table>
  <tr>
    <td colspan="4"><img src="assets/screenshots/1.png" alt="Preview screenshot #1 of Desktop, with a terminal session displaying fastfetch information."></td>
  </tr>
  <tr>
    <td colspan="1"><img src="assets/screenshots/2.png" alt="Preview screenshot #2 of Desktop, with an instance showing neovim theming and hyprpicker integration into notch."></td>
    <td colspan="1"><img src="assets/screenshots/3.png" alt="Preview screenshot #3 of Desktop, showing theme switching implementation within the bar's dashboard."></td>
    <td colspan="1"><img src="assets/screenshots/4.png" alt="Preview screenshot #4 of Desktop, showing application launcher with textbox search, integrated into the notch."></td>
    <td colspan="1"><img src="assets/screenshots/5.png" alt="Preview screenshot #5 of Desktop, showing power menu integration in notch, with lock, suspend, logout, reboot, and shutdown icon options."></td>
  </tr>
</table>

<h2><sub><img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Package.png" alt="Package" width="25" height="25" /></sub> Installation/Updating</h2>

> [!NOTE]
> You need a functioning Hyprland installation.

### Arch Linux
```bash
curl -fsSL https://raw.githubusercontent.com/dxnnv/Ax-Shell/main/install.sh | bash
```

### Manual Installation
1. Install dependencies:
    - [Fabric](https://github.com/Fabric-Development/fabric)
    - [fabric-cli](https://github.com/Fabric-Development/fabric-cli)
    - [Gray](https://github.com/Fabric-Development/gray)
    - [Matugen](https://github.com/InioX/matugen)
    - `cava`
    - `cliphist`
    - `dccutil`
    - `gobject-introspection`
    - `gpu-screen-recorder`
    - `grimblast`
    - `hypridle`
    - `hyprlock`
    - `hyprpicker`
    - `hyprshot`
    - `hyprsunset`
    - `imagemagick`
    - `libnotify`
    - `noto-fonts-emoji`
    - `nvtop`
    - `playerctl`
    - `swappy`
    - `swww`
    - `tesseract`
    - `tmux`
    - `uwsm`
    - `vte3`
    - `webp-pixbuf-loader`
    - `wl-clipboard`
    - `wlinhibit`
    - Python dependencies:
        - `PyGObject`
        - `ijson`
        - `numpy`
        - `pillow`
        - `psutil`
        - `pywayland`
        - `requests`
        - `setproctitle`
        - `toml`
        - `watchdog`
    - Fonts (automated on first run):
        - `Zed Sans`
        - `Tabler Icons`

2. Download:
    ```bash
    git clone https://github.com/dxnnv/Ax-Shell.git ~/.config/Ax-Shell
    ln -s ~/.config/Ax-Shell/shell/run_shell.sh ~/.local/bin/ax-shell
    ```
    If using uwsm, install te service:
    ```bash
    install -Dm0644 /dev/stdin "$XDG_CONFIG_HOME/systemd/user/ax-shell.service" "$XDG_CONFIG_HOME/Ax-Shell/shell/shell-template.service"
    ```

3. Run Ax-Shell:
    ```bash
    # With service (for uwsm)
    systemctl --user enable --now ax-shell
    # With executable
    ax-shell
    ```

---

<table>
  <tr>
    <td><img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Telegram-Animated-Emojis/main/Activity/Sparkles.webp" alt="Sparkles" width="16" height="16" /><sup> sᴜᴘᴘᴏʀᴛ ᴛʜᴇ ᴀᴜᴛʜᴏʀ </sup><img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Telegram-Animated-Emojis/main/Activity/Sparkles.webp" alt="Sparkles" width="16" height="16" /></td>
  </tr>
  <tr>
    <td>
      <a href='https://ko-fi.com/Axenide' target='_blank'>
        <img style='border:0px;height:128px;'
            src='https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExc3N4NzlvZWs2Z2tsaGx4aHgwa3UzMWVpcmNwZTNraTM2NW84ZDlqbiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9cw/PaF9a1MpqDzovyqVKj/giphy.gif'
            alt='Support the original author on Ko-fi!' />
      </a>
    </td>
  </tr>
</table>
