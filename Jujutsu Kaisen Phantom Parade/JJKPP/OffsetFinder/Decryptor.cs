namespace OffsetFinder
{
    public static class Decryptor
    {
        /// <summary>
        /// XOR-decrypts bytes using the repeating key (flags).
        /// </summary>
        public static byte[] Decrypt(byte[] flags, byte[] input)
        {
            if (flags == null || flags.Length == 0)
                throw new ArgumentException("Flags must not be empty.");
            var output = new byte[input.Length];
            for (int i = 0; i < input.Length; i++)
                output[i] = (byte)(input[i] ^ flags[i % flags.Length]);
            return output;
        }
    }
}
