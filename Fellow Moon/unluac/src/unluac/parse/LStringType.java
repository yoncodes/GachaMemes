package unluac.parse;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;


public abstract class LStringType extends BObjectType<LString> {

  public static LStringType50 getType50() {
    return new LStringType50();
  }
  
  public static LStringType53 getType53() {
    return new LStringType53();
  }
  
  protected ThreadLocal<List<Byte>> byteList = new ThreadLocal<List<Byte>>() {
    
    @Override
    protected List<Byte> initialValue() {
      return new ArrayList<Byte>();  
    }

  };
  
}

class LStringType50 extends LStringType {
  @Override
  public LString parse(final ByteBuffer buffer, BHeader header) {
    BSizeT sizeT = header.sizeT.parse(buffer, header);
    final List<Byte> bytes = this.byteList.get();
    bytes.clear();
    
    sizeT.iterate(new Runnable() {
      @Override
      public void run() {
        bytes.add(buffer.get());
      }
    });
    
    // Convert List<Byte> to byte[]
    byte[] byteArray = new byte[bytes.size()];
    for(int i = 0; i < bytes.size(); i++) {
      byteArray[i] = bytes.get(i);
    }
    
    // Decode as UTF-8
    String s = new String(byteArray, StandardCharsets.UTF_8);
    
    if(header.debug) {
      System.out.println("-- parsed <string> \"" + s + "\"");
    }
    return new LString(sizeT, s);
  }
}

class LStringType53 extends LStringType {
  @Override
  public LString parse(final ByteBuffer buffer, BHeader header) {
    BSizeT sizeT;
    int size = 0xFF & buffer.get();
    if(size == 0xFF) {
      sizeT = header.sizeT.parse(buffer, header);
    } else {
      sizeT = new BSizeT(size);
    }
    
    final List<Byte> bytes = this.byteList.get();
    bytes.clear();
    
    sizeT.iterate(new Runnable() {
      boolean first = true;
      
      @Override
      public void run() {
        if(!first) {
          bytes.add(buffer.get());
        } else {
          first = false;
        }
      }
    });
    
    // Add null terminator
    bytes.add((byte)0);
    
    // Convert List<Byte> to byte[]
    byte[] byteArray = new byte[bytes.size()];
    for(int i = 0; i < bytes.size(); i++) {
      byteArray[i] = bytes.get(i);
    }
    
    // Decode as UTF-8
    String s = new String(byteArray, StandardCharsets.UTF_8);
    
    if(header.debug) {
      System.out.println("-- parsed <string> \"" + s + "\"");
    }
    return new LString(sizeT, s);
  }
}