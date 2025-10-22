package unluac.parse;

public class LString extends LObject {

  public final BSizeT size;
  public final String value;

  public LString(BSizeT size, String value) {
    this.size = size;
    // Trim trailing null, if present
    this.value = value.length() == 0 ? "" : value.substring(0, value.length() - 1);
  }

  @Override
  public String deref() {
    return value;
  }

  @Override
  public String toString() {
    StringBuilder sb = new StringBuilder();
    sb.append('"');

    // Iterate through string using code points to handle UTF-8 properly
    int length = value.length();
    for (int i = 0; i < length; i++) {
      char c = value.charAt(i);
      
      // Check for special escape sequences
      if (c == '\n') {
        sb.append("\\n");
      } else if (c == '\r') {
        sb.append("\\r");
      } else if (c == '\t') {
        sb.append("\\t");
      } else if (c == '"') {
        sb.append("\\\"");
      } else if (c == '\\') {
        sb.append("\\\\");
      } else if (c >= 32 && c < 127) {
        // ASCII printable - output directly
        sb.append(c);
      } else if (c >= 127) {
        // High Unicode character (UTF-8) - output directly, DO NOT ESCAPE
        sb.append(c);
      } else {
        // Control characters (0-31, 127) - escape as decimal
        sb.append('\\');
        sb.append((int)c);
      }
    }

    sb.append('"');
    return sb.toString();
  }

  @Override
  public boolean equals(Object o) {
    if (o instanceof LString) {
      LString os = (LString) o;
      return os.value.equals(value);
    }
    return false;
  }
}