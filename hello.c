#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

typedef short (__stdcall *SPC_init_t)(char *);
typedef short (__stdcall *SPC_close_t)(void);
typedef short (__stdcall *SPC_enable_sequencer_t)(int, int);
typedef short (__stdcall *SPC_set_parameter_t)(int, int, int);
typedef short (__stdcall *SPC_configure_memory_t)(int, int, int, void *);
typedef short (__stdcall *SPC_fill_memory_t)(int, int, int, int);
typedef short (__stdcall *SPC_set_page_t)(int, int);
typedef short (__stdcall *SPC_start_measurement_t)(int);
typedef short (__stdcall *SPC_test_state_t)(int, short *);
typedef short (__stdcall *SPC_read_data_page_t)(int, int, int, unsigned short *);

#define MODE 0   // You may want to replace with actual constants from spcm_def.h
#define NORMAL 0
#define SPC_ARMED 1
#define MAX_NO_OF_SPC 1  // Adjust if you have multiple modules

// Define a minimal spc_mem_info struct for example
typedef struct {
    int max_block_no;
    int maxpage;
    int block_length;
    int blocks_per_frame;
    int frames_per_page;
} spc_mem_info_t;

int main() {
    HMODULE hDLL = LoadLibrary("C:\\Program Files (x86)\\BH\\SPCM\\DLL\\spcm64.dll");
    if (!hDLL) {
        printf("Failed to load DLL\n");
        return 1;
    }

    SPC_init_t SPC_init = (SPC_init_t)GetProcAddress(hDLL, "SPC_init");
    SPC_close_t SPC_close = (SPC_close_t)GetProcAddress(hDLL, "SPC_close");
    SPC_enable_sequencer_t SPC_enable_sequencer = (SPC_enable_sequencer_t)GetProcAddress(hDLL, "SPC_enable_sequencer");
    SPC_set_parameter_t SPC_set_parameter = (SPC_set_parameter_t)GetProcAddress(hDLL, "SPC_set_parameter");
    SPC_configure_memory_t SPC_configure_memory = (SPC_configure_memory_t)GetProcAddress(hDLL, "SPC_configure_memory");
    SPC_fill_memory_t SPC_fill_memory = (SPC_fill_memory_t)GetProcAddress(hDLL, "SPC_fill_memory");
    SPC_set_page_t SPC_set_page = (SPC_set_page_t)GetProcAddress(hDLL, "SPC_set_page");
    SPC_start_measurement_t SPC_start_measurement = (SPC_start_measurement_t)GetProcAddress(hDLL, "SPC_start_measurement");
    SPC_test_state_t SPC_test_state = (SPC_test_state_t)GetProcAddress(hDLL, "SPC_test_state");
    SPC_read_data_page_t SPC_read_data_page = (SPC_read_data_page_t)GetProcAddress(hDLL, "SPC_read_data_page");

    if (!SPC_init || !SPC_close || !SPC_enable_sequencer || !SPC_set_parameter ||
        !SPC_configure_memory || !SPC_fill_memory || !SPC_set_page || !SPC_start_measurement ||
        !SPC_test_state || !SPC_read_data_page) {
        printf("Failed to find one or more functions\n");
        FreeLibrary(hDLL);
        return 1;
    }

    short ret = SPC_init("C:\\Program Files (x86)\\BH\\SPCM\\DLL\\spcm.ini");
    printf("SPC_init returned: %d\n", ret);
    if (ret != 0) {
        printf("SPC_init failed\n");
        FreeLibrary(hDLL);
        return 1;
    }

    // Example minimal sequence based on your sample:
    ret = SPC_enable_sequencer(-1, 0);
    printf("SPC_enable_sequencer returned: %d\n", ret);

    ret = SPC_set_parameter(-1, MODE, NORMAL);
    printf("SPC_set_parameter returned: %d\n", ret);

    spc_mem_info_t mem_info;
    ret = SPC_configure_memory(-1, 8, 0, &mem_info);  // 8 = example ADC resolution, adjust as needed
    printf("SPC_configure_memory returned: %d\n", ret);

    if (ret != 0) {
        printf("SPC_configure_memory failed\n");
        SPC_close();
        FreeLibrary(hDLL);
        return 1;
    }

    ret = SPC_fill_memory(-1, -1, 0, 0);
    printf("SPC_fill_memory returned: %d\n", ret);

    ret = SPC_set_page(-1, 0);
    printf("SPC_set_page returned: %d\n", ret);

    ret = SPC_start_measurement(-1);
    printf("SPC_start_measurement returned: %d\n", ret);

    if (ret != 0) {
        printf("SPC_start_measurement failed\n");
        SPC_close();
        FreeLibrary(hDLL);
        return 1;
    }

    // Wait for measurement to finish:
    short state = 0;
    do {
        SPC_test_state(-1, &state);
        printf("Measurement state: %d\n", state);
        Sleep(1000); // Wait 1 second
    } while (state & SPC_ARMED);

    // Allocate buffer for histogram data
    int page_size = mem_info.blocks_per_frame * mem_info.frames_per_page * mem_info.block_length;
    unsigned short *buffer = malloc(page_size * sizeof(unsigned short));
    if (!buffer) {
        printf("Failed to allocate buffer\n");
        SPC_close();
        FreeLibrary(hDLL);
        return 1;
    }

    ret = SPC_read_data_page(-1, 0, 0, buffer);
    printf("SPC_read_data_page returned: %d\n", ret);

    if (ret != 0) {
        printf("SPC_read_data_page failed\n");
        free(buffer);
        SPC_close();
        FreeLibrary(hDLL);
        return 1;
    }

    // Print first 20 histogram values as example
    printf("Histogram data (first 20 bins):\n");
    for (int i = 0; i < 20; i++) {
        printf("%d: %u\n", i, buffer[i]);
    }

    free(buffer);
    SPC_close();
    FreeLibrary(hDLL);

    printf("Measurement complete\n");

    return 0;
}
