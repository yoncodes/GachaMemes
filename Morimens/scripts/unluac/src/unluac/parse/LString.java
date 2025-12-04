package unluac.parse;

import unluac.decompile.PrintFlag;
import unluac.util.StringUtils;

public class LString extends LObject {

  public static final LString NULL = new LString("");
  
  public final String value;
  public final char terminator;
  public boolean islong;
  
  public LString(String value) {    
    this(value, '\0', false);
  }
  
  public LString(String value, char terminator) {
    this(value, terminator, false);
  }
  
  public LString(String value, char terminator, boolean islong) {
    this.value = value;
    this.terminator = terminator;
    this.islong = islong;
  }
  
  @Override
  public String deref() {
    return value;
  }
  
  @Override
  public String toPrintString(int flags) {
    if(this == NULL) {
      return "null";
    } else {
  
      // --- NEW: decode \ddd decimal escape sequences ---
      String decoded = unescapeDecimalUTF8(value);
  
      String prefix = "";
      String suffix = "";
      if(islong) prefix = "L";
      if(PrintFlag.test(flags, PrintFlag.SHORT)) {
        final int LIMIT = 20;
        if(decoded.length() > LIMIT) suffix = " (truncated)";
        return prefix + StringUtils.toPrintString(decoded, LIMIT) + suffix;
      } else {
        return prefix + StringUtils.toPrintString(decoded);
      }
    }
  }

  private String unescapeDecimalUTF8(String s) {
    byte[] buffer = new byte[s.length()];
    int bi = 0;
  
    for(int i = 0; i < s.length();) {
      char c = s.charAt(i);
  
      if(c == '\\') {
        i++;
        // parse up to 3 digits (decimal escape)
        int num = 0;
        int count = 0;
        while(i < s.length() && count < 3 && Character.isDigit(s.charAt(i))) {
          num = num * 10 + (s.charAt(i) - '0');
          i++;
          count++;
        }
        buffer[bi++] = (byte)(num & 0xFF);
      } else {
        buffer[bi++] = (byte)c;
        i++;
      }
    }
  
    // decode UTF-8 bytes → Java string
    return new String(buffer, 0, bi, java.nio.charset.StandardCharsets.UTF_8);
  }
  
  
  @Override
  public boolean equals(Object o) {
    if(this == NULL || o == NULL) {
      return this == o;
    } else if(o instanceof LString) {
      LString os = (LString) o;
      return os.value.equals(value) && os.islong == islong;
    }
    return false;
  }
  
}
