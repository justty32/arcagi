// Included inside namespace seed. HOT_D only: keep scratch storage at its
// high-water capacity and append by index, with no per-element vector growth.
#pragma once
namespace {
struct ResultSlot { std::unique_ptr<V[]> values; size_t capacity = 0; };
thread_local ResultSlot result_buffers[8];
thread_local size_t result_depth = 0;
struct ResultBuffer {
    V* values;
    size_t count = 0;
    bool owned;
    __attribute__((always_inline)) explicit ResultBuffer(size_t maximum) : owned(result_depth >= 8) {
        if (owned) values = new V[maximum];
        else {
            ResultSlot& slot = result_buffers[result_depth];
            if (slot.capacity < maximum) {
                slot.values.reset(new V[maximum]);
                slot.capacity = maximum;
            }
            values = slot.values.get();
        }
        // Scalar V slots need no initialization; only appended slots are read.
        // Grow before advancing depth, so allocation failure leaves it unchanged.
        ++result_depth;
    }
    ~ResultBuffer() { --result_depth; if (owned) delete[] values; }
    void push(V value) { values[count++] = value; }
    V* data() { return values; }
    size_t size() const { return count; }
};
}  // namespace
