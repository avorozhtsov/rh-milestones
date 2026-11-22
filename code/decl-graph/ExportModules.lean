import Lean

/-!
Dump the declarations of compiled Lean modules, one module at a time.

    lean --run ExportModules.lean <list.txt> <out.tsv>

`list.txt` has one line per module: `<module name><TAB><path to .olean>`.
Each `.olean` is read on its own, without loading the modules it imports, so
memory stays small however large the project is.

Output, one line per constant, tab separated:

    module  hash  name  kind  internal  typeDeps  valueDeps

`hash` is Lean's 64-bit hash of the name. `typeDeps` and `valueDeps` are the
hashes of the constants used in the statement and in the proof or body.
-/

open Lean

def kindOf : ConstantInfo → String
  | .thmInfo _ => "thm"
  | .defnInfo _ => "def"
  | .axiomInfo _ => "axiom"
  | .opaqueInfo _ => "opaque"
  | .quotInfo _ => "quot"
  | .inductInfo _ => "ind"
  | .ctorInfo _ => "ctor"
  | .recInfo _ => "rec"

def cleanName (n : Name) : String :=
  (toString n).map fun c => if c == '\t' || c == '\n' || c == ' ' then '_' else c

def hashes (e : Expr) : String :=
  " ".intercalate (e.getUsedConstants.toList.map fun c => toString c.hash)

unsafe def main (args : List String) : IO UInt32 := do
  let [listFile, outFile] := args | do
    IO.eprintln "usage: lean --run ExportModules.lean <list.txt> <out.tsv>"
    return 2
  let lines := (← IO.FS.readFile listFile).splitOn "\n" |>.filter (· ≠ "")
  let mut done := 0
  let mut failed := 0
  let h ← IO.FS.Handle.mk outFile .write
  for line in lines do
    let [modName, path] := line.splitOn "\t" | continue
    try
      let (data, region) ← readModuleData path
      for ci in data.constants do
        let valueDeps := match ci.value? (allowOpaque := true) with
          | some v => hashes v
          | none => ""
        h.putStrLn <| "\t".intercalate
          [modName, toString ci.name.hash, cleanName ci.name, kindOf ci,
           if ci.name.isInternalDetail then "1" else "0", hashes ci.type, valueDeps]
      region.free
      done := done + 1
    catch e =>
      failed := failed + 1
      IO.eprintln s!"{modName}: {e}"
  h.flush
  IO.println s!"{done} modules exported, {failed} failed"
  return 0
