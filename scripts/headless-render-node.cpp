// Experimental Aquamarine 0.16.0 interposition for a render-node-only session.
// No DRM master, display modesetting, or host input devices are requested.
#include <cstdlib>
#include <cstring>
#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <unistd.h>
#include <gbm.h>
#include <fcntl.h>
#include <aquamarine/backend/Headless.hpp>
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl3.h>
#include <GLES2/gl2ext.h>
#include <libdrm/drm_fourcc.h>

namespace Aquamarine {

static bool virtualCursorEnabled() {
    const char* value = std::getenv("AQ_HEADLESS_VIRTUAL_CURSOR");
    return value && std::strcmp(value, "1") == 0;
}

static bool virtualCursorOutput(const IOutput* output) {
    return virtualCursorEnabled() && dynamic_cast<const CHeadlessOutput*>(output);
}

static bool readCursorGPU(const Hyprutils::Memory::CSharedPointer<IBuffer>& buffer, std::vector<uint8_t>& pixels) {
    const auto attributes = buffer->dmabuf();
    const auto display = eglGetCurrentDisplay();
    if (!attributes.success || attributes.planes != 1 || display == EGL_NO_DISPLAY) return false;
    const auto createImage = reinterpret_cast<PFNEGLCREATEIMAGEKHRPROC>(eglGetProcAddress("eglCreateImageKHR"));
    const auto destroyImage = reinterpret_cast<PFNEGLDESTROYIMAGEKHRPROC>(eglGetProcAddress("eglDestroyImageKHR"));
    const auto imageTarget = reinterpret_cast<PFNGLEGLIMAGETARGETTEXTURE2DOESPROC>(eglGetProcAddress("glEGLImageTargetTexture2DOES"));
    if (!createImage || !destroyImage || !imageTarget) return false;
    std::vector<EGLint> parameters{EGL_WIDTH, static_cast<EGLint>(buffer->size.x),
        EGL_HEIGHT, static_cast<EGLint>(buffer->size.y), EGL_LINUX_DRM_FOURCC_EXT, static_cast<EGLint>(attributes.format),
        EGL_DMA_BUF_PLANE0_FD_EXT, attributes.fds[0], EGL_DMA_BUF_PLANE0_OFFSET_EXT, static_cast<EGLint>(attributes.offsets[0]),
        EGL_DMA_BUF_PLANE0_PITCH_EXT, static_cast<EGLint>(attributes.strides[0])};
    if (attributes.modifier != DRM_FORMAT_MOD_INVALID) {
        parameters.insert(parameters.end(), {EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT, static_cast<EGLint>(attributes.modifier),
            EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT, static_cast<EGLint>(attributes.modifier >> 32)});
    }
    parameters.push_back(EGL_NONE);
    const auto image = createImage(display, EGL_NO_CONTEXT, EGL_LINUX_DMA_BUF_EXT, nullptr, parameters.data());
    if (image == EGL_NO_IMAGE_KHR) return false;
    GLint oldTexture, oldDrawFB, oldReadFB, oldPackBuffer;
    GLint packAlignment, packRowLength, packSkipRows, packSkipPixels;
    glGetIntegerv(GL_TEXTURE_BINDING_2D, &oldTexture);
    glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &oldDrawFB);
    glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &oldReadFB);
    glGetIntegerv(GL_PIXEL_PACK_BUFFER_BINDING, &oldPackBuffer);
    glGetIntegerv(GL_PACK_ALIGNMENT, &packAlignment);
    glGetIntegerv(GL_PACK_ROW_LENGTH, &packRowLength);
    glGetIntegerv(GL_PACK_SKIP_ROWS, &packSkipRows);
    glGetIntegerv(GL_PACK_SKIP_PIXELS, &packSkipPixels);
    GLuint texture = 0, framebuffer = 0;
    glGenTextures(1, &texture);
    glBindTexture(GL_TEXTURE_2D, texture);
    imageTarget(GL_TEXTURE_2D, image);
    glGenFramebuffers(1, &framebuffer);
    glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture, 0);
    bool success = glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE;
    if (success) {
        pixels.resize(static_cast<size_t>(buffer->size.x * buffer->size.y * 4));
        glBindBuffer(GL_PIXEL_PACK_BUFFER, 0);
        glPixelStorei(GL_PACK_ALIGNMENT, 1);
        glPixelStorei(GL_PACK_ROW_LENGTH, 0);
        glPixelStorei(GL_PACK_SKIP_ROWS, 0);
        glPixelStorei(GL_PACK_SKIP_PIXELS, 0);
        glReadPixels(0, 0, buffer->size.x, buffer->size.y, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
        success = glGetError() == GL_NO_ERROR;
    }
    glBindBuffer(GL_PIXEL_PACK_BUFFER, oldPackBuffer);
    glPixelStorei(GL_PACK_ALIGNMENT, packAlignment);
    glPixelStorei(GL_PACK_ROW_LENGTH, packRowLength);
    glPixelStorei(GL_PACK_SKIP_ROWS, packSkipRows);
    glPixelStorei(GL_PACK_SKIP_PIXELS, packSkipPixels);
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, oldDrawFB);
    glBindFramebuffer(GL_READ_FRAMEBUFFER, oldReadFB);
    glBindTexture(GL_TEXTURE_2D, oldTexture);
    glDeleteFramebuffers(1, &framebuffer);
    glDeleteTextures(1, &texture);
    destroyImage(display, image);
    return success;
}

static void exportVirtualCursor(const Hyprutils::Memory::CSharedPointer<IBuffer>& buffer,
                                const Hyprutils::Math::Vector2D& hotspot) {
    const char* runtime = std::getenv("XDG_RUNTIME_DIR");
    if (!runtime) return;
    uint32_t width = 0, height = 0;
    std::vector<uint8_t> pixels;
    if (buffer) {
        width = buffer->size.x;
        height = buffer->size.y;
        if (!width || !height || width > 512 || height > 512) return;
        // NVIDIA cursor BOs need not be CPU-mappable. Read only this tiny shape
        // through EGL; the desktop capture/encode path stays zero-copy.
        std::vector<uint8_t> readback;
        uint8_t* data;
        uint32_t format;
        size_t bytes;
        const bool mapped = !readCursorGPU(buffer, readback);
        if (mapped) std::tie(data, format, bytes) = buffer->beginDataPtr(GBM_BO_TRANSFER_READ);
        else { data = readback.data(); format = DRM_FORMAT_ABGR8888; bytes = readback.size(); }
        if (!data || bytes < width * height * 4 ||
            (format != DRM_FORMAT_ARGB8888 && format != DRM_FORMAT_ABGR8888)) {
            if (mapped && data) buffer->endDataPtr();
            static bool reported = false;
            if (!reported) {
                std::fprintf(stderr, "Headless cursor: shape readback unavailable\n");
                reported = true;
            }
            return;
        }
        const size_t stride = bytes / height;
        pixels.resize(width * height * 4);
        for (uint32_t y = 0; y < height; ++y) {
            for (uint32_t x = 0; x < width; ++x) {
                const auto* source = data + y * stride + x * 4;
                auto* target = pixels.data() + (y * width + x) * 4;
                const unsigned alpha = source[3];
                for (unsigned channel = 0; channel < 3; ++channel) {
                    const unsigned index = format == DRM_FORMAT_ARGB8888 ? 2 - channel : channel;
                    target[channel] = alpha ? std::min(255U, (source[index] * 255U + alpha / 2) / alpha) : 0;
                }
                target[3] = alpha;
            }
        }
        if (mapped) buffer->endDataPtr();
    }
    // Private, atomic shape-only snapshot. Mouse positions never cross this
    // file; the browser already knows those and renders movement immediately.
    const std::vector<uint32_t> header{0x5255434F, width, height,
        static_cast<uint32_t>(static_cast<int32_t>(hotspot.x)),
        static_cast<uint32_t>(static_cast<int32_t>(hotspot.y)), buffer ? 1U : 0U};
    static std::vector<uint32_t> previousHeader;
    static std::vector<uint8_t> previousPixels;
    if (header == previousHeader && pixels == previousPixels) return;
    const std::string path = std::string(runtime) + "/omarchy-headless-cursor.bin";
    const std::string temporary = path + ".tmp-" + std::to_string(getpid());
    const int fd = open(temporary.c_str(), O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (fd < 0) return;
    const auto writeAll = [fd](const void* bytes, size_t length) {
        auto* data = static_cast<const uint8_t*>(bytes);
        while (length) {
            const auto count = write(fd, data, length);
            if (count < 0 && errno == EINTR) continue;
            if (count <= 0) return false;
            data += count;
            length -= count;
        }
        return true;
    };
    const bool written = writeAll(header.data(), header.size() * sizeof(uint32_t)) &&
                         writeAll(pixels.data(), pixels.size());
    close(fd);
    if (written && rename(temporary.c_str(), path.c_str()) == 0) {
        previousHeader = header;
        previousPixels = std::move(pixels);
    } else unlink(temporary.c_str());
}

// A headless output has no physical cursor plane. When explicitly enabled,
// accept a separate logical plane so Hyprland does not bake its software cursor
// into the output texture. Capture protocols can still request cursor painting,
// and the private adapter channel exports the real shape and hotspot.
uint32_t CHeadlessBackend::capabilities() {
    return virtualCursorEnabled() ? AQ_BACKEND_CAPABILITY_POINTER : 0;
}

std::vector<SDRMFormat> CHeadlessBackend::getCursorFormats() {
    if (!virtualCursorEnabled()) return {};
    auto formats = getRenderFormats();
    std::erase_if(formats, [](const SDRMFormat& format) {
        return format.drmFormat != DRM_FORMAT_ARGB8888 && format.drmFormat != DRM_FORMAT_ABGR8888;
    });
    return formats;
}

bool IOutput::hasCursorPlane() const {
    return virtualCursorOutput(this);
}

Hyprutils::Math::Vector2D IOutput::cursorPlaneSize() {
    return virtualCursorOutput(this) ? Hyprutils::Math::Vector2D{-1, -1} : Hyprutils::Math::Vector2D{};
}

bool IOutput::setCursor(Hyprutils::Memory::CSharedPointer<IBuffer> buffer, const Hyprutils::Math::Vector2D& hotspot) {
    if (!virtualCursorOutput(this)) return false;
    exportVirtualCursor(buffer, hotspot);
    return true;
}

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
