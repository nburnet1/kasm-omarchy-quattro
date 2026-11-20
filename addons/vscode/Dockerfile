FROM kasm-omarchy-quattro:4.5.0-essentials
USER root
RUN omarchy-pkg-add visual-studio-code-bin \
    && ln -sf /usr/share/applications/com.microsoft.VSCode.desktop /usr/local/share/applications/code.desktop
COPY --chmod=755 configure-code.sh /dockerstartup/profile.d/50-vscode.sh
LABEL org.omarchy.kasm.addons="vscode"
USER 1000
