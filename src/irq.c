#include "irq.h"

#include <stdbool.h>
#include <c64/rasterirq.h>

void irq_init(void) {
    rirq_init(true);
    rirq_start();
}
