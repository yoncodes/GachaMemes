using Mono.Cecil;
using Mono.Cecil.Rocks;
using static FbsDumper.MainApp;

namespace FbsDumper;

internal class TypeHelper
{
    private InstructionsParser instructionsResolver = new InstructionsParser(MainApp.LibIl2CppPath);

    public List<TypeDefinition> GetAllFlatBufferTypes(ModuleDefinition module, string baseTypeName)
    {
        List<TypeDefinition> ret = module.GetTypes().Where(t =>
            t.HasInterfaces &&
            t.Interfaces.Any(i => i.InterfaceType.FullName == baseTypeName)
			//  && t.FullName == "MX.Data.Excel.MinigameRoadPuzzleMapExcel"
		).ToList();

        if (!String.IsNullOrEmpty(MainApp.NameSpace2LookFor))
        {
            ret = ret.Where(t => t.Namespace == MainApp.NameSpace2LookFor).ToList();
        }

        // Dedupe
        ret = ret
            .GroupBy(t => t.Name)
            .Select(g => g.First())
            .ToList();

        // Add standalone enums if in the same namespace
        var allEnums = module.Types
            .Where(t => t.IsEnum &&
                (string.IsNullOrEmpty(MainApp.NameSpace2LookFor) ||
                 t.Namespace == MainApp.NameSpace2LookFor))
            .ToList();

        foreach (var enumType in allEnums)
        {
            if (!MainApp.flatEnumsToAdd.Contains(enumType))
                MainApp.flatEnumsToAdd.Add(enumType);
        }

        return ret;

    }

    public FlatTable? Type2Table(TypeDefinition targetType)
    {
        string typeName = targetType.Name;
        FlatTable ret = new FlatTable(typeName);

       
        MethodDefinition? createMethod = targetType.Methods.FirstOrDefault(m =>
            m.Name == $"Create{typeName}" &&
            m.Parameters.Count > 1 &&
            m.Parameters.First().Name == "builder" &&
            m.IsStatic &&
            m.IsPublic
        );

        if (createMethod != null)
        {
            ProcessFields(ref ret, createMethod, targetType);
        }
        else
        {
            if (targetType.IsInterface)
            {
                ExtractFromInterface(targetType, ref ret);
            }
            else
            {
                var addMethods = targetType.Methods
                    .Where(m =>
                        m.IsStatic &&
                        m.Name.StartsWith("Add") &&
                        m.Parameters.Count == 2 &&
                        m.Parameters[0].ParameterType.FullName.Contains("FlatBuffers.FlatBufferBuilder"))
                    .ToList();

                if (addMethods.Count > 0)
                {
                    foreach (var add in addMethods)
                    {
                        string fieldName = add.Parameters[1].Name;
                        TypeReference fieldTypeRef = add.Parameters[1].ParameterType;
                        TypeDefinition fieldType = fieldTypeRef.Resolve();

                        if (fieldType.FullName.StartsWith("FlatBuffers."))
                        {
                            string baseName = fieldName.EndsWith("Offset")
                                ? fieldName.Substring(0, fieldName.Length - "Offset".Length)
                                : fieldName;
                            fieldName = baseName.Replace("_", "");
                            fieldType = targetType.Module.TypeSystem.String.Resolve();
                        }

                        var field = new FlatField(fieldType, fieldName)
                        {
                            offset = ret.fields.Count
                        };
                        ret.fields.Add(field);
                    }
                }
                else
                {
                    if (targetType.Methods.Any(m => m.IsStatic && m.Name.StartsWith("Add")))
                    {
                        
                        ProcessFieldsByMethods(ref ret, targetType);
                    }
                    else if (targetType.Interfaces.Any(i => i.InterfaceType.FullName == FlatBaseType))
                    {
                        ExtractFromClassProperties(targetType, ref ret);
                    }
                    else
                    {
                        ret.noCreate = true;
                    }
                }

            }
        }


        return ret;
    }


    private void ExtractFromInterface(TypeDefinition targetType, ref FlatTable ret)
    {
        // Handles interface-only types such as IMasterScoreBattleHp
        // by converting their property signatures into FlatField entries.

        foreach (var prop in targetType.Properties)
        {
            var typeRef = prop.PropertyType;
            var typeDef = typeRef.Resolve();
            bool isArray = false;

      
            if (typeRef is GenericInstanceType genericInstance)
            {
                var inner = genericInstance.GenericArguments.FirstOrDefault();
                if (inner != null)
                {
                    typeRef = inner;
                    typeDef = inner.Resolve();
                    isArray = true;
                }
            }

            // create a FlatField for this property
            var flatField = new FlatField(typeDef, prop.Name)
            {
                offset = ret.fields.Count,
                isArray = isArray
            };

            // record enums for later inclusion
            if (typeDef.IsEnum && !MainApp.flatEnumsToAdd.Contains(typeDef))
                MainApp.flatEnumsToAdd.Add(typeDef);

            ret.fields.Add(flatField);
        }
    }

    private void ExtractFromClassProperties(TypeDefinition targetType, ref FlatTable ret)
    {
        // Handles wrapper classes (no Create/Add methods) that expose FlatBuffer-like fields
        foreach (var prop in targetType.Properties)
        {
            if (!prop.GetMethod?.IsPublic ?? true)
                continue; // skip non-public getters

            var typeRef = prop.PropertyType;
            var typeDef = typeRef.Resolve();
            bool isArray = false;

            if (typeRef is GenericInstanceType genericInstance)
            {
                var inner = genericInstance.GenericArguments.FirstOrDefault();
                if (inner != null)
                {
                    typeRef = inner;
                    typeDef = inner.Resolve();
                    isArray = true;
                }
            }

            var flatField = new FlatField(typeDef, prop.Name)
            {
                offset = ret.fields.Count,
                isArray = isArray
            };

            if (typeDef.IsEnum && !MainApp.flatEnumsToAdd.Contains(typeDef))
                MainApp.flatEnumsToAdd.Add(typeDef);

            ret.fields.Add(flatField);
        }
    }

    public static void ProcessFieldsByMethods(ref FlatTable ret, TypeDefinition targetType)
    {
        // find all AddXXX static methods
        var addMethods = targetType.Methods
            .Where(m => m.IsStatic && m.Name.StartsWith("Add"))
            .OrderBy(m => m.MetadataToken.ToInt32()) // roughly preserves source order
            .ToList();

        int index = 0;
        foreach (var method in addMethods)
        {
            var param = method.Parameters.LastOrDefault();
            if (param == null) continue;

            var fieldName = method.Name.Substring(3); // strip "Add"
            var fieldType = param.ParameterType.Resolve();

            ret.fields.Add(new FlatField(fieldType, fieldName)
            {
                offset = index++
            });
        }
    }


    private void ProcessFields(ref FlatTable ret, MethodDefinition createMethod, TypeDefinition targetType)
    {
        var parameters = createMethod.Parameters
            .Skip(1) // skip the builder param
            .ToList();

        // collect param info with optional metadata offset
        var paramInfos = new List<(int order, ParameterDefinition param)>();

        foreach (var param in parameters)
        {
            int order = int.MaxValue; // fallback order
            foreach (var attr in param.CustomAttributes)
            {
                if (attr.AttributeType.Name == "MetadataOffsetAttribute" && attr.ConstructorArguments.Count > 0)
                {
                    var val = attr.ConstructorArguments[0].Value?.ToString();
                    if (!string.IsNullOrEmpty(val) && val.StartsWith("0x"))
                    {
                        order = Convert.ToInt32(val, 16);
                    }
                }
            }

            paramInfos.Add((order, param));
        }

        // sort by metadata offset
        paramInfos = paramInfos.OrderBy(p => p.order).ToList();

        foreach (var (order, param) in paramInfos)
        {
            var fieldName = param.Name;
            var fieldTypeRef = param.ParameterType;
            var fieldType = fieldTypeRef.Resolve();
            bool isArray = false;

            // unwrap generics like List<T> or IReadOnlyList<T>
            if (fieldTypeRef is GenericInstanceType genericInstance)
            {
                var inner = genericInstance.GenericArguments.FirstOrDefault();
                if (inner != null)
                {
                    fieldTypeRef = inner;
                    fieldType = inner.Resolve();
                    isArray = true;
                }
            }

            // map FlatBuffers offset wrappers (StringOffset, Offset<T>, VectorOffset)
            if (fieldType.FullName.StartsWith("FlatBuffers."))
            {
                string rawName = fieldName;
                string baseName = rawName.EndsWith("Offset")
                    ? rawName.Substring(0, rawName.Length - "Offset".Length)
                    : rawName;

                baseName = baseName.Replace("_", "");

                switch (fieldType.Name)
                {
                    case "StringOffset":
                        fieldType = targetType.Module.TypeSystem.String.Resolve();
                        fieldTypeRef = targetType.Module.TypeSystem.String;
                        break;
                    case "Offset`1":
                    case "VectorOffset":
                        isArray = fieldType.Name == "VectorOffset";
                        var accessor = targetType.Methods
                            .FirstOrDefault(m => string.Equals(m.Name, baseName, StringComparison.OrdinalIgnoreCase));
                        if (accessor != null)
                        {
                            fieldTypeRef = accessor.ReturnType;
                            fieldType = fieldTypeRef.Resolve();
                        }
                        break;
                }

                fieldName = baseName;
            }

            // make FlatField
            var flatField = new FlatField(fieldType, fieldName)
            {
                offset = order,
                isArray = isArray
            };

            // enqueue enum type for schema dump
            if (fieldType.IsEnum && !MainApp.flatEnumsToAdd.Contains(fieldType))
            {
                MainApp.flatEnumsToAdd.Add(fieldType);
            }

            ret.fields.Add(flatField);
        }

        
        bool allInvalid = ret.fields.All(f => f.offset == int.MaxValue);
        if (allInvalid)
        {
            Console.WriteLine($"[WARN] {targetType.Name} Create method invalid (all 0x7FFFFFFF offsets) — falling back to AddXXX scan.");

            // clear invalid fields
            ret.fields.Clear();

            // Fallback to AddXXX scan
            ProcessFieldsByMethods(ref ret, targetType);

            // Optional: sort fallback fields in AddXXX declaration order
            ret.fields = ret.fields
                .OrderBy(f => f.offset)
                .ToList();
        }
    }


    public Dictionary<int, MethodDefinition> ParseCalls4CreateMethod(MethodDefinition createMethod, TypeDefinition targetType)
    {
        Dictionary<int, MethodDefinition> ret = new Dictionary<int, MethodDefinition>();
        Dictionary<long, MethodDefinition> typeMethods = new Dictionary<long, MethodDefinition>();

        foreach (MethodDefinition method in targetType.GetMethods())
        {
            long rva = InstructionsParser.GetMethodRVA(method);
            typeMethods.Add(rva, method);
        }

		var instructions = instructionsResolver.GetInstructions(createMethod, false);
		InstructionsAnalyzer processer = new InstructionsAnalyzer();
		var calls = processer.AnalyzeCalls(instructions);
		bool hasStarted = false;
        int max = 0;
        int cur = 0;

        MethodDefinition endMethod = targetType.Methods.First(m => m.Name == $"End{targetType.Name}");
        long endMethodRVA = InstructionsParser.GetMethodRVA(endMethod);

		foreach (var call in calls)
		{
            long target = long.Parse(call.Target.Substring(3), System.Globalization.NumberStyles.HexNumber);
			switch (target)
            {
                case long addr when addr == flatBufferBuilder.StartObject:
                    hasStarted = true;
                    string arg1 = call.Args["w1"];
					int cnt = arg1.StartsWith("#") ? int.Parse(arg1.Substring(3), System.Globalization.NumberStyles.HexNumber) : 0;
                    max = cnt;
					// Console.WriteLine($"Has started, instance will have {cnt} fields");
                    break;
				case long addr when addr == flatBufferBuilder.EndObject:
					// Console.WriteLine($"Has ended");
					return ret;
                case long addr when addr == endMethodRVA:
					// Console.WriteLine($"Stop");
					return ret;
				default:
                    if (!hasStarted)
                    {
                        Console.WriteLine($"Skipping call for 0x{target:X} because StartObject hasn't been called yet");
                    }
                    if (!typeMethods.TryGetValue(target, out MethodDefinition? method) || method == null)
					{
						Console.WriteLine($"Skipping call for 0x{target:X} because it's not part of the {targetType.FullName}");
						continue;
                    }
                    if (cur >= max)
                    {
						Console.WriteLine($"Skipping call for 0x{target:X} because max amount of fields has been reached");
						continue;
					}
                    int index = ParseCalls4AddMethod(method, targetType);
                    ret.Add(index, method);
                    cur += 1;
					continue;
			}
		}

        return ret;
	}

    public int ParseCalls4AddMethod(MethodDefinition createMethod, TypeDefinition targetType)
    {
		var instructions = instructionsResolver.GetInstructions(createMethod, false);
		InstructionsAnalyzer processer = new InstructionsAnalyzer();
        var calls = processer.AnalyzeCalls(instructions);
        var call = calls.First(m => flatBufferBuilder.methods.ContainsKey(long.Parse(m.Target.Substring(3), System.Globalization.NumberStyles.HexNumber)));
		string arg1 = call.Args["w1"];
		int cnt = arg1.StartsWith("#") ? int.Parse(arg1.Substring(3), System.Globalization.NumberStyles.HexNumber) : 0;
		// Console.WriteLine($"Index is {cnt}");
		return cnt;
    }

	public static FlatEnum Type2Enum(TypeDefinition typeDef)
    {
        TypeDefinition retType = typeDef.GetEnumUnderlyingType().Resolve();
        FlatEnum ret = new FlatEnum(retType, typeDef.Name);

        foreach (FieldDefinition fieldDef in typeDef.Fields.Where(f => f.HasConstant))
        {
            FlatEnumField enumField = new FlatEnumField(fieldDef.Name, Convert.ToInt64(fieldDef.Constant));
            ret.fields.Add(enumField);
        }

        return ret;
    }
}
