import Mathlib

/-!
Dump the declaration dependency graph of everything imported here.

Run from the `mathlib-graph` folder:

    GRAPH_OUT=../data/mathlib_decls.tsv lake env lean MathlibGraph/Export.lean

One line per constant, tab separated:

    id  name  kind  module  internal  typeDeps  valueDeps

`typeDeps` are the constants used in the statement (the type), `valueDeps` the
constants used in the proof or definition body. Both are space separated ids.
-/

open Lean Elab Command

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

def idList (ids : Std.HashMap Name Nat) (e : Expr) : String :=
  " ".intercalate (e.getUsedConstants.toList.filterMap fun c => (ids.get? c).map toString)

run_cmd do
  let env ← getEnv
  let out := (← IO.getEnv "GRAPH_OUT").getD "decls.tsv"
  let (ids, names) := env.constants.fold (init := (({} : Std.HashMap Name Nat), (#[] : Array Name)))
    fun (ids, names) n _ => (ids.insert n names.size, names.push n)
  IO.FS.withFile out .write fun h => do
    for n in names do
      let some ci := env.find? n | continue
      let modName := match env.getModuleIdxFor? n with
        | some i => toString env.header.moduleNames[i.toNat]!
        | none => ""
      let valueDeps := match ci.value? (allowOpaque := true) with
        | some v => idList ids v
        | none => ""
      h.putStrLn <| "\t".intercalate
        [toString (ids.get! n), cleanName n, kindOf ci, modName,
         if n.isInternalDetail then "1" else "0", idList ids ci.type, valueDeps]
  logInfo m!"wrote {names.size} constants to {out}"
