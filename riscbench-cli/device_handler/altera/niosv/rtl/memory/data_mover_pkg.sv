package data_mover_pkg;

    typedef struct packed {
        // DDR read request
        logic        read_valid;
        logic [31:0] read_address;
        logic [31:0] read_words;

        // DDR write request
        logic        write_valid;
        logic [31:0] write_address;
        logic [31:0] write_words;

        logic [7:0]  burst_len;
    } buffered_request_t;

    typedef struct packed {
        logic [31:0] read_offset;
        logic [31:0] write_offset;
        // Input buffer selection
        logic load_a;
        logic load_b;

        // Local buffer access from compute
        logic [31:0] a_read_address;
        logic [31:0] b_read_address;

        logic        c_write_enable;
        logic [31:0] c_write_address;
        logic [31:0] c_write_data;
        logic [31:0] c_read_address;
    } local_buffer_request_t;

    typedef struct packed {
        logic read_ready;
        logic write_ready;
        logic read_busy;
        logic write_busy;
        logic read_done;
        logic write_done;
    } buffered_response_t;

    typedef struct packed {
        logic [31:0] a_data;
        logic [31:0] b_data;
        logic [31:0] c_data;
    } local_buffer_response_t;

    typedef struct packed {
        logic        read_valid;
        logic        write_valid;
        logic [31:0] address;
        logic [31:0] write_data;
    } word_request_t;

    typedef struct packed {
        logic        ready;
        logic        read_valid;
        logic [31:0] read_data;
    } word_response_t;

endpackage