# Compiler
CC = gcc

# Output directory
OUTDIR = output

# Flags
CFLAGS = -Ixlua
LDFLAGS = -Lxlua -llua

# ---- Targets ----
all: $(OUTDIR) $(OUTDIR)/morimendec.exe

# Create output dir
$(OUTDIR):
	if not exist $(OUTDIR) mkdir $(OUTDIR)

# --- dec.exe build ---
DEC_SRCS = main.c \
	decryptor/decrypt_file.c \
	decryptor/proto.c \
	decryptor/varint.c \
	decryptor/crypto.c \
	decryptor/bytecode.c \
	decryptor/summary.c \
	decryptor/validator.c \
	decryptor/opcode.c

$(OUTDIR)/morimendec.exe: $(DEC_SRCS)
	$(CC) $(CFLAGS) -o $@ $(DEC_SRCS) xlua/liblua.a


# Cleanup (Windows)
clean:
	if exist $(OUTDIR)\*.exe del /Q $(OUTDIR)\*.exe
