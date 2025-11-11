# TypeScript Type Auto-Discovery System

*How TypeScript automatically finds and uses `.d.ts` declaration files to provide type information*

## The Core Mechanism

**What's ACTUALLY happening at the fundamental level?**

TypeScript's type discovery is a file resolution system that maps JavaScript code to type declarations. The mechanism works through a multi-stage lookup process:

1. **Declaration files (`.d.ts`)** contain only type signatures - no implementation. They're a "contract" that describes the shape of JavaScript code.

2. **The resolution algorithm** searches for type information in a specific order when TypeScript encounters an import or reference:
   - For local files: Look in the same directory
   - For npm packages: Check inside the package itself (via `package.json` metadata)
   - For npm packages without bundled types: Check `@types/` scope packages

3. **The matching system** uses filename correspondence:
   - `mylib.js` → looks for `mylib.d.ts`
   - `mylib.ts` → TypeScript compiler generates type info directly
   - Package name `express` → looks for `node_modules/express/` types or `node_modules/@types/express/`

4. **Package.json metadata** acts as a pointer:
   - `types` or `typings` field tells TypeScript where to find declarations
   - If absent, TypeScript falls back to convention-based lookup

The mechanism enables JavaScript libraries to be used with full type safety - the declarations layer exists independently from the implementation layer.

---

## Logical Architecture

**How do the components fit together systematically?**

The type discovery system has two distinct paths:

### Local File Resolution
```
User imports: ./server.js
  ↓
TypeScript checks: same directory for server.d.ts
  ↓
If found: Load type declarations
If not found: Infer types from .js (if allowJs: true) or treat as 'any'
```

### NPM Package Resolution
```
User imports: express
  ↓
1. Check node_modules/express/package.json
   → Look for "types" or "typings" field
   → If found: Use specified path (e.g., "./index.d.ts")
   ↓
2. If no types field, check for index.d.ts next to main entry
   ↓
3. If package has no types, check @types scope
   → Search node_modules/@types/express/
   → Look for package.json → types field → declarations
   ↓
4. Walk up directory tree checking all node_modules/@types/ folders
   → /project/node_modules/@types/
   → /project/src/node_modules/@types/
   → /node_modules/@types/
   ↓
5. Can override with typeRoots in tsconfig.json
```

### Configuration Layer
```
tsconfig.json provides control:
  ↓
typeRoots: Defines which directories to search
  Default: ["node_modules/@types"]
  Custom: ["./typings", "./node_modules/@types"]
  ↓
types: Whitelist specific packages (blocks auto-inclusion)
  Default: Include all @types packages
  Custom: ["node", "jest"] (only these)
  ↓
include/exclude: Which files TypeScript processes
```

### The @types Ecosystem
```
DefinitelyTyped (community type definitions)
  ↓
Published to npm as @types/<package-name>
  ↓
Installed alongside JavaScript packages
  ↓
Auto-discovered by TypeScript
  ↓
Provides types for untyped JavaScript libraries
```

---

## Mental Model

**The simplified representation you hold in your head**

Think of TypeScript's type discovery as a **"shadow file system"** for types:

**For local files:**
- Every `.js` file has an optional `.d.ts` shadow in the same folder
- TypeScript always looks for the shadow first
- Shadow contains the type "blueprint" of the implementation

**For npm packages:**
- TypeScript uses a two-tier lookup: "package itself" then "@types scope"
- Like checking "does this package ship with types?" then "does the community provide types?"
- Package.json acts as a "types pointer" telling TypeScript where to look

**Configuration as filters:**
- `typeRoots` = "where to look for types"
- `types` = "which types to actually include"
- Like setting search paths and whitelists

**The @types pattern:**
- @types/express shadows the express package
- Convention: `@types/<package-name>` mirrors `<package-name>`
- Allows types and implementation to evolve independently

**Key insight:** Types are a separate layer that "maps onto" JavaScript code. The discovery system is about maintaining this mapping automatically.

---

## Connections

**Links to other knowledge bases and concepts**

**Built from:**
- File system resolution patterns (how Node.js resolves modules)
- Package.json as metadata specification (npm conventions)
- Convention-over-configuration principle (sensible defaults with override capability)

**Links to:**
- Module resolution systems (similar to how Node.js resolves imports)
- Source maps (another "shadow file" pattern for debugging)
- API contracts and interface definition languages (types as contracts)

**Enables:**
- Writing type-safe code while using untyped JavaScript libraries
- Gradual TypeScript adoption (add types to existing JS projects)
- IDE autocomplete and IntelliSense (powered by type discovery)
- Static analysis tools (linters, type checkers)

**Compare with:**
- Flow's type discovery (Facebook's alternative system, similar but different scoping)
- JSDoc type annotations (inline types vs. separate declaration files)
- C/C++ header files (.h files are analogous to .d.ts files)

**Examples of analogous patterns in other domains:**
- C header files (.h) and implementation (.c) - same separation of interface and implementation
- Java interfaces vs. implementations - contract vs. behavior split
- API specifications (OpenAPI/Swagger) describing REST endpoints - documentation layer separate from code

---

## Derivation Path

**How did you build this understanding?**

1. **Initial question:** "How does TypeScript know about types in JavaScript libraries?"
   - Surface understanding: something about .d.ts files

2. **First exploration:** What ARE .d.ts files?
   - Discovery: They're declaration-only files (no implementation)
   - They provide type signatures for JavaScript code

3. **Key question:** How does TypeScript FIND these files?
   - Started with simple case: local files
   - Learned: same directory, filename matching

4. **Complexity emerged:** What about npm packages?
   - Multiple lookup locations
   - Package.json metadata
   - @types scope pattern

5. **Aha moment:** It's a multi-tier fallback system!
   - Check package itself first (bundled types)
   - Fall back to community types (@types)
   - Walk up directory tree

6. **Configuration layer:** How to override defaults?
   - typeRoots for search paths
   - types for whitelisting
   - include/exclude for file filtering

7. **Mental model crystalized:** "Shadow file system for types"
   - Types map onto implementation
   - Discovery maintains this mapping
   - Configuration controls the mapping rules

8. **Connection to broader patterns:** Recognized similarity to:
   - C header files
   - Source maps
   - Any system with interface/implementation separation

---

## Edge Cases / Limitations

**Where does this model break or not apply?**

**Local files:**
- Only searches same directory (doesn't walk up tree for local imports)
- No fallback to @types for local files
- Must explicitly specify .d.ts if you want types for a local .js file

**Package resolution conflicts:**
- If package has bundled types AND @types package exists, bundled types win
- Can cause confusion if @types package is more up-to-date
- Solution: Remove @types package if library now ships types

**typeRoots override:**
- Specifying typeRoots REPLACES defaults (doesn't extend)
- Must explicitly include "node_modules/@types" if you want default behavior
- Easy to accidentally break auto-discovery

**types array whitelist:**
- Specifying `types: ["node"]` blocks all other @types packages
- Auto-inclusion stops working
- Must explicitly list every @types package you need

**Monorepos and nested node_modules:**
- TypeScript walks up directory tree, but this can be slow
- Symlinked packages (like in pnpm) can confuse resolution
- May need custom typeRoots configuration

**Declaration file quality:**
- .d.ts files can be wrong or outdated
- TypeScript trusts declarations blindly
- No validation that .d.ts matches actual .js behavior

**Doesn't handle:**
- Runtime type checking (TypeScript types are compile-time only)
- Types for dynamically generated code
- Types for code loaded at runtime (eval, dynamic import of unknown modules)
- Non-JavaScript languages without custom type definitions

**Assumptions that must hold:**
- Package names match between implementation and @types
- Declaration files are accurate
- File system structure follows conventions
- npm/node_modules structure is standard

---

## Status

**Confidence:** High

**Last Updated:** 2025-11-11

**Areas Needing Refinement:**
- Exact precedence rules when multiple type sources exist (bundled + @types + typeRoots)
- How pnpm's symlink structure affects type resolution
- Workspace-specific type resolution in monorepos
- How ESM vs CommonJS affects .d.ts resolution

**Next Steps:**
- Test type resolution in edge cases (nested node_modules, workspaces)
- Explore TypeScript's module resolution strategies (Classic vs. Node)
- Understand how .d.ts generation works from TypeScript source
- Investigate how type resolution affects build performance

---

## Additional Context

**This knowledge base was extracted from:** Conversation about TypeScript's .d.ts auto-discovery system

**Related documentation:**
- TypeScript Handbook: Module Resolution
- DefinitelyTyped repository
- npm @types scope documentation

**Practical applications:**
- Setting up TypeScript in existing JavaScript projects
- Publishing npm packages with types
- Debugging "Cannot find module" errors
- Optimizing TypeScript build performance