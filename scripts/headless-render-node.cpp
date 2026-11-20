// Experimental Aquamarine 0.16.0 interposition for a render-node-only session.
// No DRM master, display modesetting, or host input devices are requested.
#include <cstdlib>
#include <fcntl.h>
#include <aquamarine/backend/Misc.hpp>
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <libdrm/drm_fourcc.h>

namespace Aquamarine {
class CHeadlessBackend {
public:
    int drmFD();
    int drmRenderNodeFD();
    std::vector<SDRMFormat> getRenderFormats();
};

int CHeadlessBackend::drmFD() {
    static int fd = [] {
        const char* path = std::getenv("AQ_HEADLESS_RENDER_NODE");
        return path ? open(path, O_RDWR | O_CLOEXEC) : -1;
    }();
    return fd;
}

int CHeadlessBackend::drmRenderNodeFD() {
    return drmFD();
}

std::vector<SDRMFormat> CHeadlessBackend::getRenderFormats() {
    std::vector<SDRMFormat> result;
    auto query = reinterpret_cast<PFNEGLQUERYDMABUFMODIFIERSEXTPROC>(eglGetProcAddress("eglQueryDmaBufModifiersEXT"));
    for (auto format : {DRM_FORMAT_XRGB8888, DRM_FORMAT_ARGB8888, DRM_FORMAT_XBGR8888, DRM_FORMAT_ABGR8888}) {
        SDRMFormat entry{format, {}};
        EGLint count = 0;
        auto display = eglGetCurrentDisplay();
        if (query && display != EGL_NO_DISPLAY && query(display, format, 0, nullptr, nullptr, &count) && count > 0) {
            std::vector<EGLuint64KHR> mods(count);
            std::vector<EGLBoolean> external(count);
            query(display, format, count, mods.data(), external.data(), &count);
            for (int i = 0; i < count; ++i)
                if (!external[i]) entry.modifiers.push_back(mods[i]);
        }
        if (!entry.modifiers.empty()) result.push_back(entry);
    }
    return result;
}
}
