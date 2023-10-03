{% macro row_input( type, name, label ) %}
<div class="form-group row">
    <label class="col-sm-4 text-nowrap">{{ label }}</label>
    <div class="col-sm-8"><input type="{{ type }}" name="{{ name }}" class="form-control" /></div>
</div>
{% endmacro %}

{% macro row_select( name, label, options, selected=none, size=1 ) %}
<div class="form-group row">
    <label class="col-sm-4 text-nowrap">{{ label }}</label>
    <div class="col-sm-8">
    <select size="{{ size }}" name="{{ name }}" class="form-select">
    {% if options is mapping %}
        {% for k,v in options|dictsort(false,'value') %}
        <option value="{{ k }}"{% if k == selected %} selected{% endif %}>{{ v }}</option>
        {% endfor %}
    {% elif options is sequence %}
        {% for v in options %}
        <option value="{{ v }}"{% if v == selected %} selected{% endif %}>{{ v }}</option>
        {% endfor %}
    {% endif %}
    </select>
    </div>
</div>
{% endmacro %}

{% macro row_submitbtn_right( text ) %}
<div class="form-group row">
    <div class="col-sm-12 d-flex flex-row-reverse"><button type="submit" class="btn btn-primary">{{ text }}</button></div>
</div>
{% endmacro %}

