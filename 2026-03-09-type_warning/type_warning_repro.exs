defmodule DirectCallRepro do
  @moduledoc false

  def test do
    pub(:one, "hi")
  end

  def pub(interval, voicing) do
    priv(:ok, interval, voicing)
  end

  defp priv(state, interval, voicing) when is_atom(interval) and is_list(voicing) do
    state
  end
end

defmodule ClosureCallRepro do
  @moduledoc false

  def test do
    pub(:one, "hi")
  end

  def pub(interval, voicing) do
    fun = &priv(&1, interval, voicing)
    fun.(:ok)
  end

  defp priv(state, interval, voicing) when is_atom(interval) and is_list(voicing) do
    state
  end
end

# Run with:
#   elixir type_warning_repro.exs
#
# Expected on Elixir 1.20.0-rc.2:
# - DirectCallRepro.test/0 emits a type warning for pub/2
# - ClosureCallRepro.test/0 does not emit a type warning
