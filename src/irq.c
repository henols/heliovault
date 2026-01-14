#include "irq.h"

#include <stdbool.h>
#include <stdint.h>
#include <c64/rasterirq.h>

static volatile uint8_t* const VIC_IRQ_ENABLE = (uint8_t*)0xD01A;
static volatile uint8_t* const VIC_IRQ_STATUS = (uint8_t*)0xD019;
static volatile uint8_t* const CIA1_IRQ_CTRL = (uint8_t*)0xDC0D;
static volatile uint8_t* const CIA2_IRQ_CTRL = (uint8_t*)0xDD0D;

void kernal_irq_disable(void) {
    __asm {
        sei
    }
    *VIC_IRQ_ENABLE = 0;
    *VIC_IRQ_STATUS = 0x0F;
    *CIA1_IRQ_CTRL = 0x7F;
    *CIA2_IRQ_CTRL = 0x7F;
    (void)*CIA1_IRQ_CTRL;
    (void)*CIA2_IRQ_CTRL;
}

void irq_init(void) {
    // Avoid KERNAL IRQ vector chaining during early startup; reduces reset/return-to-BASIC.
    rirq_init(false);
    // Temporarily disable raster IRQ start to isolate startup crashes.
    // rirq_start();
}
