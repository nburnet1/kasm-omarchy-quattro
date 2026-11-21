// The pinned pixelflux external-compositor pointer sends time=0. Qt uses the
// Wayland event time to recognize double clicks and rejects such click pairs.
// Repair missing timestamps at the headless compositor's protocol boundary;
// preserve nonzero client timestamps and the original device/seat/dispatch.
#include <wayland-server-core.h>
#include <dlfcn.h>
#include <time.h>
#include <cstdint>
#include <cstring>
#include <unordered_map>

namespace {
// Request ABI of zwlr_virtual_pointer_v1, protocol versions 1 and 2.
struct PointerRequests {
    void (*motion)(wl_client*, wl_resource*, uint32_t, wl_fixed_t, wl_fixed_t);
    void (*absolute)(wl_client*, wl_resource*, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t);
    void (*button)(wl_client*, wl_resource*, uint32_t, uint32_t, uint32_t);
    void (*axis)(wl_client*, wl_resource*, uint32_t, uint32_t, wl_fixed_t);
    void (*frame)(wl_client*, wl_resource*);
    void (*source)(wl_client*, wl_resource*, uint32_t);
    void (*stop)(wl_client*, wl_resource*, uint32_t, uint32_t);
    void (*discrete)(wl_client*, wl_resource*, uint32_t, uint32_t, wl_fixed_t, int32_t);
    void (*destroy)(wl_client*, wl_resource*);
};

struct PointerState {
    PointerRequests original;
    PointerRequests repaired;
    wl_resource_destroy_func_t destroy;
};

auto& pointers() {
    // Resources may be destroyed during library shutdown. Keep this registry
    // alive for the compositor process; each resource removes its own entry.
    static auto* states = new std::unordered_map<wl_resource*, PointerState>;
    return *states;
}

uint32_t timestamp(uint32_t clientTime) {
    if (clientTime) return clientTime;
    timespec now{};
    clock_gettime(CLOCK_MONOTONIC, &now);
    return static_cast<uint32_t>(static_cast<uint64_t>(now.tv_sec) * 1000 + now.tv_nsec / 1000000);
}

void motion(wl_client* c, wl_resource* r, uint32_t t, wl_fixed_t x, wl_fixed_t y) {
    pointers().at(r).original.motion(c, r, timestamp(t), x, y);
}
void absolute(wl_client* c, wl_resource* r, uint32_t t, uint32_t x, uint32_t y, uint32_t w, uint32_t h) {
    pointers().at(r).original.absolute(c, r, timestamp(t), x, y, w, h);
}
void button(wl_client* c, wl_resource* r, uint32_t t, uint32_t b, uint32_t s) {
    pointers().at(r).original.button(c, r, timestamp(t), b, s);
}
void axis(wl_client* c, wl_resource* r, uint32_t t, uint32_t a, wl_fixed_t v) {
    pointers().at(r).original.axis(c, r, timestamp(t), a, v);
}
void stop(wl_client* c, wl_resource* r, uint32_t t, uint32_t a) {
    pointers().at(r).original.stop(c, r, timestamp(t), a);
}
void discrete(wl_client* c, wl_resource* r, uint32_t t, uint32_t a, wl_fixed_t v, int32_t d) {
    pointers().at(r).original.discrete(c, r, timestamp(t), a, v, d);
}
void destroyed(wl_resource* resource) {
    auto found = pointers().find(resource);
    if (found == pointers().end()) return;
    const auto original = found->second.destroy;
    pointers().erase(found);
    if (original) original(resource);
}
}

extern "C" void wl_resource_set_implementation(wl_resource* resource, const void* implementation,
                                               void* data, wl_resource_destroy_func_t destroy) {
    using SetImplementation = decltype(&wl_resource_set_implementation);
    static auto original = reinterpret_cast<SetImplementation>(dlsym(RTLD_NEXT, "wl_resource_set_implementation"));
    const char* name = wl_resource_get_class(resource);
    if (!implementation || !name || std::strcmp(name, "zwlr_virtual_pointer_v1") != 0 ||
        wl_resource_get_version(resource) > 2) {
        original(resource, implementation, data, destroy);
        return;
    }
    auto& state = pointers()[resource];
    state.original = *static_cast<const PointerRequests*>(implementation);
    state.repaired = state.original;
    state.destroy = destroy;
    state.repaired.motion = motion;
    state.repaired.absolute = absolute;
    state.repaired.button = button;
    state.repaired.axis = axis;
    state.repaired.stop = stop;
    state.repaired.discrete = discrete;
    original(resource, &state.repaired, data, destroyed);
}
