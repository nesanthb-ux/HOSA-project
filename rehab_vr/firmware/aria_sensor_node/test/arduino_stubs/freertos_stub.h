#pragma once
// FreeRTOS pieces the sketch uses. In the real ESP32 core these come in through
// Arduino.h; here they are forced in with -include for the compile check.
#include <stddef.h>
#include <stdint.h>

typedef void* QueueHandle_t;
typedef void (*TaskFunction_t)(void*);
#define pdTRUE 1
#define portMAX_DELAY 0xFFFFFFFFu
inline QueueHandle_t xQueueCreate(int, int) { return nullptr; }
inline int xQueueOverwrite(QueueHandle_t, const void*) { return pdTRUE; }
inline int xQueueReceive(QueueHandle_t, void*, uint32_t) { return 0; }
inline int xTaskCreatePinnedToCore(TaskFunction_t, const char*, uint32_t, void*, int, void*, int) { return pdTRUE; }
